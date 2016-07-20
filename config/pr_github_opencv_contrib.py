import os
import re
from twisted.python import log
from twisted.internet import defer

from buildbot.process.properties import Properties

from github import GitHub

import pr_github_opencv

import constants

userAgent = pr_github_opencv.userAgent
githubAccessToken = pr_github_opencv.githubAccessToken

class GitHubContext(pr_github_opencv.GitHubContext):

    statusRepoId = 'contrib'
    statusUrl = 'http://pullrequest.opencv.org/#/summary/contrib'

    updatePullRequestsDelay = 30

    name = 'GitHub Pull Requests for opencv_contrib'
    dbname = '/data/db/pullrequests_github_opencv_contrib'

    urlpath = 'pullrequests_gh_contrib'

    builders = dict(
        linux=dict(name='Linux x64', builders=['precommit-contrib_linux64'], order=10),
        windows=dict(name='Win7 x64 VS2013', builders=['precommit-contrib_windows64'], order=20),
        windows10=dict(name='Win10 x64 VS2015', builders=['precommit-contrib_windows_ten'], order=25),
        macosx=dict(name='Mac', builders=['precommit-contrib_macosx'], order=30),
        android=dict(name='Android armeabi-v7a', builders=['precommit-contrib_android'], order=40),
        docs=dict(name='Docs', builders=['precommit-contrib_docs'], order=90),
        ios=dict(name='iOS', builders=['precommit-contrib_ios'], order=100),

        # Optional
        win32=dict(name='Win32', builders=['precommit-contrib_windows32'], order=1100),
        armv7=dict(name='ARMv7', builders=['precommit-contrib_armv7'], order=1200),
        armv8=dict(name='ARMv8', builders=['precommit-contrib_armv8'], order=1300),
        ocl=dict(name='OpenCL', builders=['precommit-contrib_opencl'], order=2100),
        oclIntel=dict(name='OpenCL Intel', builders=['precommit_opencl-intel'], order=2200),
        linuxNoOpt=dict(name='Linux x64 Debug', builders=['precommit-contrib_linux64_no_opt'], order=5100),
        android_pack=dict(name='Android pack', builders=['precommit-contrib_pack_android'], order=10040),
    )

    username = 'opencv'
    repo = 'opencv_contrib'

    def getListOfAutomaticBuilders(self, pr):
        if self.isWIP(pr) or os.environ.get('DEBUG', False) or os.environ.get('BUILDBOT_MANUAL', False):
            return []
        buildersList = [
            'linux',
            'windows',
            'macosx',
            'android',
            'docs',
            'ios',
            'windows10'
        ]
        return buildersList

    @defer.inlineCallbacks
    def getBuildProperties(self, pr, b, properties, sourcestamps):
        if not self.isBadBranch(pr):
            if not ((yield self.readOtherPR(pr, 'opencv_extra', 'extra')) and
                    (yield self.readOtherPR(pr, 'opencv', 'main'))):
                defer.returnValue(False)

        properties.setProperty('branch', pr.branch, 'Pull request')
        properties.setProperty('head_sha', pr.head_sha, 'Pull request')
        properties.setProperty('pullrequest', pr.prid, 'Pull request')
        # regressionTestFilter = self.extractRegressionTestFilter(pr.description)

        sourcestamps.append(dict(
            codebase='opencv',
            #repository='https://github.com/%s/opencv.git' % (self.username),
            repository='%sopencv.git' % constants.URL_GIT_BASE,
            branch=pr.branch))

        if str(pr.info.get('main', None)) == '1':
            sourcestamps.append(dict(
                codebase='opencv_merge',
                repository='https://github.com/%s/%s.git' % (pr.head_user, 'opencv'),
                branch=pr.head_branch,
                revision=pr.head_sha))

        sourcestamps.append(dict(
            codebase='opencv_contrib',
            #repository='https://github.com/%s/%s.git' % (self.username, self.repo),
            repository='%s%s.git' % (constants.URL_GIT_BASE, self.repo),
            branch=pr.branch))

        sourcestamps.append(dict(
            codebase='opencv_contrib_merge',
            repository='https://github.com/%s/%s.git' % (pr.head_user, pr.head_repo),
            branch=pr.head_branch,
            revision=pr.head_sha))

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


context = GitHubContext()
