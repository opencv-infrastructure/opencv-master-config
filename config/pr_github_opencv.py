import os
import re
from pprint import pprint

from twisted.python import log
from twisted.internet import defer, reactor, task

from buildbot.process.properties import Properties

from github import GitHub, GitHubCommitStatus

import pullrequest.context
from pullrequest.utils import JSONClient

import constants

userAgent = 'BuildBot GitHub PullRequest v1.0'
githubAccessToken = os.environ.pop('GITHUB_APIKEY')

class GitHubContext(pullrequest.context.Context):

    githubStatusAccessToken = os.environ.pop('GITHUB_STATUS_APIKEY', None)
    statusRepoId = 'opencv'
    statusUrl = 'http://pullrequest.opencv.org/#/summary/opencv'

    updatePullRequestsDelay = 30

    name = 'GitHub Pull Requests'
    dbname = '/data/db/pullrequests_github_opencv'

    urlpath = 'pullrequests_gh'

    builders = dict(
        linux=dict(name='Linux x64', builders=['precommit_linux64'], order=10),
        windows=dict(name='Win7 x64 VS2013', builders=['precommit_windows64'], order=20),
        windows10=dict(name='Win10 x64 VS2015', builders=['precommit_windows_ten'], order=25),
        macosx=dict(name='Mac', builders=['precommit_macosx'], order=30),
        android=dict(name='Android armeabi-v7a', builders=['precommit_android'], order=40),
        ocl=dict(name='OpenCL', builders=['precommit_opencl'], order=50),
        oclIntel=dict(name='OpenCL Intel', builders=['precommit_opencl-intel'], order=55),
        linuxNoOpt=dict(name='Linux x64 Debug', builders=['precommit_linux64_no_opt'], order=80),
        docs=dict(name='Docs', builders=['precommit_docs'], order=90),
        ios=dict(name='iOS', builders=['precommit_ios'], order=100),

        # Optional
        win32=dict(name='Win32', builders=['precommit_windows32'], order=1100),
        armv7=dict(name='ARMv7', builders=['precommit_armv7'], order=1200),
        armv8=dict(name='ARMv8', builders=['precommit_armv8'], order=1300),
        android_pack=dict(name='Android pack', builders=['precommit_pack_android'], order=10040),
    )

    username = 'opencv'
    repo = 'opencv'

    client = None

    @defer.inlineCallbacks
    def updatePullRequests(self):
        print 'Updating pull requests from GitHub...'

        if not self.client:
            self.client = GitHub(userAgent=userAgent, async=True, reuseETag=True, access_token=githubAccessToken)
        gh_pullrequests = yield self.client.repos(self.username)(self.repo).pulls.get(state='open', per_page=100)
        if self.client.status == 304:
            print "GitHub pull requests are not changed"
            defer.returnValue(None)
        elif self.client.status == 200:
            prs = []
            for gh_pullrequest in gh_pullrequests:
                try:
                    pr = {}
                    pr['id'] = gh_pullrequest['number']
                    pr['branch'] = gh_pullrequest['base']['ref']
                    pr['author'] = gh_pullrequest['user']['login']
                    pr['assignee'] = gh_pullrequest['assignee']['login'] if gh_pullrequest['assignee'] else None
                    pr['head_user'] = gh_pullrequest['head']['repo']['owner']['login']
                    pr['head_repo'] = gh_pullrequest['head']['repo']['name']
                    pr['head_branch'] = gh_pullrequest['head']['ref']
                    pr['head_sha'] = gh_pullrequest['head']['sha']
                    pr['title'] = gh_pullrequest['title'] or ''
                    pr['description'] = gh_pullrequest['body'] or ''
                    prs.append(pr)
                except:
                    pprint(gh_pullrequest)
                    log.err()
            defer.returnValue(prs)
        raise Exception('invalid status', self.client.status)

    def getListOfAutomaticBuilders(self, pr):
        if self.isWIP(pr) or os.environ.get('DEBUG', False) or os.environ.get('BUILDBOT_MANUAL', False):
            return []
        buildersList = [
            'linux',
            'windows',
            'macosx',
            'android',
            'docs',
            'ocl',
            'linuxNoOpt',
            'ios',
            'windows10'
        ]
        return buildersList

    @defer.inlineCallbacks
    def readOtherPR(self, pr, repoName, propName):
        prid = pr.prid
        try:
            gh = GitHub(userAgent=userAgent, async=True, access_token=githubAccessToken)
            result = yield gh.repos(pr.head_user)(repoName)('branches')(pr.head_branch).get()
            if gh.x_ratelimit_remaining == 0:
                print 'GitHub API limit exceeded'
                defer.returnValue(False)
            if gh.status == 200 and result.has_key('name'):
                print 'PR #%d: %s branch found' % (prid, repoName)
                pr.info[propName] = '1'
                yield self.db.prcc.updatePullRequest(pr)
            elif gh.status == 404:
                print 'PR #%d: %s branch not found' % (prid, repoName)
                pr.info[propName] = '0'
                yield self.db.prcc.updatePullRequest(pr)
            else:
                raise Exception('Unsupported HTTP status=%d' % gh.status)
        except defer._DefGen_Return:
            raise
        except:
            log.err()
        defer.returnValue(True)

    def isBadBranch(self, pr):
        return pr.head_branch == 'master' or pr.head_branch == '2.4'

    def isWIP(self, pr):
        if hasattr(pr, 'description') and pr.description:
            if '**WIP**' in pr.description or '__WIP__' in pr.description:
                return True
        return False

    @defer.inlineCallbacks
    def getBuildProperties(self, pr, b, properties, sourcestamps):
        if not self.isBadBranch(pr):
            if not ((yield self.readOtherPR(pr, 'opencv_extra', 'extra')) and
                    (yield self.readOtherPR(pr, 'opencv_contrib', 'contrib'))):
                defer.returnValue(False)

        properties.setProperty('branch', pr.branch, 'Pull request')
        properties.setProperty('head_sha', pr.head_sha, 'Pull request')
        properties.setProperty('pullrequest', pr.prid, 'Pull request')
        if b.isPerf:
            regressionTestFilter = self.extractRegressionTestFilter(pr.description)
            if regressionTestFilter is not None:
                properties.setProperty('regression_test_filter', regressionTestFilter, 'Pull request')
            else:
                print 'ERROR: Can\'t schedule perf precommit build without regression test filter. Use check_regression parameter'
                defer.returnValue(False)

        if self.isWIP(pr):
            self.pushBuildProperty(properties, pr.description, 'test_module[s]?', 'modules_filter')
            self.pushBuildProperty(properties, pr.description, 'test[s]?_filter[s]?', 'test_filter')
            self.pushBuildProperty(properties, pr.description, 'build_examples', 'build_examples')

        sourcestamps.append(dict(
            codebase='opencv',
            #repository='https://github.com/%s/%s.git' % (self.username, self.repo),
            repository='%s%s.git' % (constants.URL_GIT_BASE, self.repo),
            branch=pr.branch))

        sourcestamps.append(dict(
            codebase='opencv_merge',
            repository='https://github.com/%s/%s.git' % (pr.head_user, pr.head_repo),
            branch=pr.head_branch,
            revision=pr.head_sha))

        sourcestamps.append(dict(
            codebase='opencv_contrib',
            repository='%sopencv_contrib.git' % constants.URL_GIT_BASE,
            branch=pr.branch))

        if str(pr.info.get('contrib', None)) == '1':
            sourcestamps.append(dict(
                codebase='opencv_contrib_merge',
                repository='https://github.com/%s/%s_contrib.git' % (pr.head_user, pr.head_repo),
                branch=pr.head_branch,
                revision=pr.head_branch))

        sourcestamps.append(dict(
            codebase='opencv_extra',
            #repository='https://github.com/%s/%s.git' % (self.username, 'opencv_extra'),
            repository='%s%s.git' % (constants.URL_GIT_BASE, 'opencv_extra'),
            branch=pr.branch))

        if str(pr.info.get('extra', None)) == '1':
            sourcestamps.append(dict(
                codebase='opencv_extra_merge',
                repository='https://github.com/%s/%s.git' % (pr.head_user, 'opencv_extra'),
                branch=pr.head_branch,
                revision=pr.head_branch))


        defer.returnValue(True)

    def getWebAddressPullRequest(self, pr):
        return 'https://github.com/%s/%s/pull/%s' % (self.username, self.repo, pr.prid)

    def getWebAddressPerfRegressionReport(self, pr):
        return None

    @defer.inlineCallbacks
    def _updateGitHubStatus(self, prid):
        if self.githubStatusAccessToken is None:
            return
        if hasattr(self, 'statusRepoId'):
            pr = yield self.db.prcc.getPullRequest(prid)

            c = JSONClient("http://master.ocv/api", userAgent=userAgent)
            res = yield c.queryFast.get(prId=prid, repoId=self.statusRepoId)

            status = 'failure'
            if res:
                msg = res['messageFast']
                if 'passed' in msg:
                    status = 'success'
                elif 'Unsuccessful build' in msg:
                    status = 'error'
                elif 'Waiting' in msg:
                    status = 'pending'
                gh = GitHub(userAgent=userAgent, access_token=self.githubStatusAccessToken)
                upd = GitHubCommitStatus(gh, self.username, self.repo)
                res = yield upd.updateCommit(pr.head_sha, status, msg, self.statusUrl)

    def onUpdatePullRequest(self, prid):
        task.deferLater(reactor, 30, self._updateGitHubStatus, prid)
        return self._updateGitHubStatus(prid)

context = GitHubContext()
