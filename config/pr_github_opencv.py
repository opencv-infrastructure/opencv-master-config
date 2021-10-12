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
        ocllinux=dict(name='Linux OpenCL', builders=['precommit_opencl_linux'], order=11),
        l_native=dict(name='Linux AVX2', builders=['precommit_linux64-avx2'], order=12),
        windows=dict(name='Win64', builders=['precommit_windows64'], order=20),
        ocl=dict(name='Win64 OpenCL', builders=['precommit_opencl'], order=21),
        macosx=dict(name='Mac', builders=['precommit_macosx'], order=30),
        android=dict(name='Android armeabi-v7a', builders=['precommit_android'], order=40),
        linuxNoOpt=dict(name='Linux x64 Debug', builders=['precommit_linux64_no_opt'], order=50),
        docs=dict(name='Docs', builders=['precommit_docs'], order=90),
        ios=dict(name='iOS', builders=['precommit_ios'], order=100),

        # Optional
        linux32=dict(name='Linux32', builders=['precommit_linux32'], order=1000),
        win32=dict(name='Win32', builders=['precommit_windows32'], order=1100),
        armv7=dict(name='ARMv7', builders=['precommit_armv7'], order=1200),
        armv8=dict(name='ARMv8', builders=['precommit_armv8'], order=1300),
        android_pack=dict(name='Android pack', builders=['precommit_pack_android'], order=10040),

        custom=dict(name='Custom', builders=['precommit_custom_linux'], order=1000000),
        #custom_lin=dict(name='Custom Lin', builders=['precommit_custom_linux'], order=1000010),
        custom_win=dict(name='Custom Win', builders=['precommit_custom_windows'], order=1000011),
        custom_mac=dict(name='Custom Mac', builders=['precommit_custom_mac'], order=1000012),
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
            #print("Fetched PRs: " + str(len(gh_pullrequests)) + " ETag=" + str(self.client.ETag))
            for gh_pullrequest in gh_pullrequests:
                # FIXIT: workaround GitHub bug 2021-10-07
                #print("Fetched PR: " + str(gh_pullrequest['number']) + " SHA=" + str( gh_pullrequest['head']['sha']))
                #if str(gh_pullrequest['number']) in ['3006', '20825']:
                #    print('!!! ERROR: Reject malformed GitHub answer !!!')
                #    defer.returnValue(None)
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

    def getBuilderIDs(self, names):
        blist = []
        names_to_ids = dict([(str(v['name']).lower(), n) for (n, v) in self.builders.items()])
        for n in names:
            if n in self.builders:
                blist.append(n)
                continue
            k = str(n).lower()
            if k in names_to_ids:
                blist.append(names_to_ids[k])
                continue
            print("Can't find builder with name: {}".format(n))
        return blist

    def validateBuildersParameter(self, name, value):
        if re.search(r'\\[^a-zA-Z0-9_]', value):
            raise ValueError('Parameter {} check failed (escape rule): "{}"'.format(name, value))
        for s in value:
            if not s.isdigit() and not s.isalpha() and s not in [',', ' ', '-', '_']:
                raise ValueError('Parameter {} check failed: "{}"'.format(name, value))
        return value

    def getListOfAutomaticBuilders(self, pr):
        if os.environ.get('DEBUG', False) or os.environ.get('BUILDBOT_MANUAL', False):
            return []
        force_builders_only_parameter = self.extractParameterEx(pr.description, 'force_builders_only', validationFn=self.validateBuildersParameter, allowSpaces=True)
        if force_builders_only_parameter:
            return self.getBuilderIDs(str(force_builders_only_parameter[1]).split(','))
        force_builders = []
        force_builders_parameter = self.extractParameterEx(pr.description, 'force_builders', validationFn=self.validateBuildersParameter, allowSpaces=True)
        if force_builders_parameter:
            force_builders = self.getBuilderIDs(str(force_builders_parameter[1]).split(','))
        if self.isBadBranch(pr):
            return force_builders
        if self.isWIP(pr):
            return force_builders
        buildersList = [
            'linux',
            'windows',
            'macosx',
            'android',
            'docs',
            'linuxNoOpt',
            'ios',
        ] + ([] if pr.branch == '2.4' else [
            'ocllinux',
            'ocl',
            #'oclmacosx',
        ])
        return buildersList + force_builders

    @defer.inlineCallbacks
    def readOtherPR(self, pr, repoName, branch_name, propName):
        prid = pr.prid
        try:
            gh = GitHub(userAgent=userAgent, async=True, access_token=githubAccessToken)
            result = yield gh.repos(pr.head_user)(repoName)('branches')(branch_name).get()
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
        if pr.branch in [
            '2.4',  # EOL in 2020
        ]:
            return True
        if pr.head_branch in [
            'master',
            '2.4',
            '3.4',
            '4.x',
            'next',
        ]:
            return True
        return False

    def isWIP(self, pr):
        if hasattr(pr, 'description') and pr.description:
            if '**WIP**' in pr.description or '__WIP__' in pr.description:
                return True
        return False

    def applyBuildCommonOptions(self, pr, b, properties, sourcestamps):
        properties.setProperty('branch', pr.branch, 'Pull request')
        if str(pr.prid) == '18279':  # FIXIT: remove this
            properties.setProperty('branch', 'next', 'Pull request (next)')
        properties.setProperty('head_sha', pr.head_sha, 'Pull request')
        properties.setProperty('pullrequest', pr.prid, 'Pull request')
        if b.isPerf:
            regressionTestFilter = self.extractRegressionTestFilter(pr.description)
            if regressionTestFilter is not None:
                properties.setProperty('regression_test_filter', regressionTestFilter, 'Pull request')
            else:
                print 'ERROR: Can\'t schedule perf precommit build without regression test filter. Use check_regression parameter'
                defer.returnValue(False)

        re_builder = re.escape(b.name)

        def _processProperty(regex, prop_name):
            if self.pushBuildProperty(properties, pr.description, regex + '[-:]' + re_builder, prop_name) is None:
                self.pushBuildProperty(properties, pr.description, regex, prop_name)

        def _processPropertyWIP(regex, prop_name):
            if self.pushBuildProperty(properties, pr.description, regex + '[-:]' + re_builder, prop_name) is None:
                if isWIP:
                    self.pushBuildProperty(properties, pr.description, regex, prop_name)

        _processProperty('ci_branch', 'ci-branch')

        isWIP = self.isWIP(pr)
        if isWIP or b.name in ['Custom', 'custom', 'Custom Lin', 'Custom Win', 'Custom Mac']:
            _processPropertyWIP('test_module[s]?', 'modules_filter')
            _processPropertyWIP('test[s]?_filter[s]?', 'test_filter')
            _processPropertyWIP('build_examples', 'build_examples')
            _processPropertyWIP('CXXFLAGS', 'build_cxxflags')
            _processPropertyWIP('CXXFLAGS_EXTRA', 'build_cxxflags_extra')
            _processPropertyWIP('CPU_BASELINE', 'build_cpu_baseline')
            _processPropertyWIP('CPU_DISPATCH', 'build_cpu_dispatch')
            _processPropertyWIP('build_compiler', 'build_compiler')
            _processPropertyWIP('build_platform', 'build_platform')
            _processPropertyWIP('build_debug', 'build_debug')

        self.pushBuildProperty(properties, pr.description, 'test_bigdata[-:]' + re_builder, 'test_bigdata')

        _processProperty('test_module[s]?_force', 'modules_force')

        self.pushBuildProperty(properties, pr.description, 'docker_image[-:]' + re_builder, 'build_image')
        self.pushBuildProperty(properties, pr.description, 'build_image[-:]' + re_builder, 'build_image')

        _processProperty('buildworker', 'buildworker')

        _processProperty('build_upload', 'build_upload')

        _processProperty('build_tbb', 'build_tbb')
        _processProperty('with_tbb', 'with_tbb')
        _processProperty('disable_ipp', 'disable_ipp')

        _processProperty('build_world', 'build_world')
        _processProperty('build_shared', 'build_shared')
        _processProperty('build_contrib', 'build_contrib')
        _processProperty('build_pkgconfig', 'build_pkgconfig')

        _processProperty('build_parallel_tests', 'parallel_tests')
        _processProperty('test_timeout', 'test_timeout')
        _processProperty('test_maxtime', 'test_maxtime')

        self.pushBuildProperty(properties, pr.description, 'linter_checks', 'linter_checks')

        _processProperty('test_opencl', 'test_opencl')

        _processProperty('android_pack_config', 'android_pack_config')  # Android
        _processProperty('test_gradle', 'test_gradle')  # Android

        _processProperty('build_gapi_standalone', 'build_gapi_standalone')


    @defer.inlineCallbacks
    def getBuildProperties(self, pr, b, properties, sourcestamps):
        extra_branch_name_parameter = self.extractParameterEx(pr.description, 'opencv_extra')
        extra_branch_name = pr.head_branch
        if extra_branch_name_parameter:
            extra_branch_name = extra_branch_name_parameter[1]

        contrib_branch_name_parameter = self.extractParameterEx(pr.description, 'opencv_contrib')
        contrib_branch_name = pr.head_branch
        if contrib_branch_name_parameter:
            contrib_branch_name = contrib_branch_name_parameter[1]

        if not self.isBadBranch(pr) or extra_branch_name_parameter:
            if not (yield self.readOtherPR(pr, 'opencv_extra', extra_branch_name, 'extra')):
                defer.returnValue(False)

        if not self.isBadBranch(pr) or contrib_branch_name_parameter:
            if not (yield self.readOtherPR(pr, 'opencv_contrib', contrib_branch_name, 'contrib')):
                defer.returnValue(False)

        try:
            self.applyBuildCommonOptions(pr, b, properties, sourcestamps)
        except:
            log.err()
            raise

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
                branch=contrib_branch_name,
                revision=contrib_branch_name))

        sourcestamps.append(dict(
            codebase='opencv_extra',
            #repository='https://github.com/%s/%s.git' % (self.username, 'opencv_extra'),
            repository='%s%s.git' % (constants.URL_GIT_BASE, 'opencv_extra'),
            branch=pr.branch))

        if str(pr.info.get('extra', None)) == '1':
            sourcestamps.append(dict(
                codebase='opencv_extra_merge',
                repository='https://github.com/%s/%s.git' % (pr.head_user, 'opencv_extra'),
                branch=extra_branch_name,
                revision=extra_branch_name))

        defer.returnValue(True)

    def getWebAddressPullRequest(self, pr):
        return 'https://github.com/%s/%s/pull/%s' % (self.username, self.repo, pr.prid)

    def getWebAddressPerfRegressionReport(self, pr):
        return None

    @defer.inlineCallbacks
    def _updateGitHubStatus(self, prid):
        print('Updating PR status: %s ...' % prid)
        if self.githubStatusAccessToken is None:
            return
        try:
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
        except:
            log.err()
            pass

    def onUpdatePullRequest(self, prid):
        task.deferLater(reactor, 5, self._updateGitHubStatus, prid)
        task.deferLater(reactor, 35, self._updateGitHubStatus, prid)  # merge service may cache old data, so retry again after cache expiration (~30 seconds)
        return None  # don't wait (yield) for status update completion, to avoid processing hangs on connection issues

context = GitHubContext()
