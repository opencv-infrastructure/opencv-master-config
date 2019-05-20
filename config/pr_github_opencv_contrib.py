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
        windows=dict(name='Win64', builders=['precommit-contrib_windows64'], order=20),
        macosx=dict(name='Mac', builders=['precommit-contrib_macosx'], order=30),
        android=dict(name='Android armeabi-v7a', builders=['precommit-contrib_android'], order=40),
        docs=dict(name='Docs', builders=['precommit-contrib_docs'], order=90),
        ios=dict(name='iOS', builders=['precommit-contrib_ios'], order=100),

        # Optional
        win32=dict(name='Win32', builders=['precommit-contrib_windows32'], order=1100),
        armv7=dict(name='ARMv7', builders=['precommit-contrib_armv7'], order=1200),
        armv8=dict(name='ARMv8', builders=['precommit-contrib_armv8'], order=1300),
        ocl=dict(name='Win64 OpenCL', builders=['precommit-contrib_opencl'], order=2100),
        ocllinux=dict(name='Linux OpenCL', builders=['precommit-contrib_opencl_linux'], order=2200),
        oclmacosx=dict(name='Mac OpenCL', builders=['precommit-contrib_opencl_macosx'], order=2300),
        linuxNoOpt=dict(name='Linux x64 Debug', builders=['precommit-contrib_linux64_no_opt'], order=5100),
        android_pack=dict(name='Android pack', builders=['precommit-contrib_pack_android'], order=10040),

        #linux_icc=dict(name='Linux x64 Intel Compiler', builders=['precommit-contrib_linux64-icc'], order=50010),
        #windows_icc=dict(name='Win64 Intel Compiler', builders=['precommit-contrib_windows64-icc'], order=50020),

        #cuda=dict(name='CUDA', builders=['precommit-contrib_cuda_linux64'], order=100000),

        custom=dict(name='Custom', builders=['precommit-contrib_custom_linux64'], order=1000000),
    )

    username = 'opencv'
    repo = 'opencv_contrib'

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
            'win32',
            'macosx',
            'android',
            'docs',
            'ios',
        ]
        return buildersList + force_builders

    @defer.inlineCallbacks
    def getBuildProperties(self, pr, b, properties, sourcestamps):
        extra_branch_name_parameter = self.extractParameterEx(pr.description, 'opencv_extra')
        extra_branch_name = pr.head_branch
        if extra_branch_name_parameter:
            extra_branch_name = extra_branch_name_parameter[1]

        main_branch_name_parameter = self.extractParameterEx(pr.description, 'opencv')
        main_branch_name = pr.head_branch
        if main_branch_name_parameter:
            main_branch_name = main_branch_name_parameter[1]

        if not self.isBadBranch(pr) or extra_branch_name_parameter:
            if not (yield self.readOtherPR(pr, 'opencv_extra', extra_branch_name, 'extra')):
                defer.returnValue(False)

        if not self.isBadBranch(pr) or main_branch_name_parameter:
            if not (yield self.readOtherPR(pr, 'opencv', main_branch_name, 'main')):
                defer.returnValue(False)

        properties.setProperty('branch', pr.branch, 'Pull request')
        properties.setProperty('head_sha', pr.head_sha, 'Pull request')
        properties.setProperty('pullrequest', pr.prid, 'Pull request')

        try:
            self.applyBuildCommonOptions(pr, b, properties, sourcestamps)
        except:
            log.err()
            raise

        sourcestamps.append(dict(
            codebase='opencv',
            #repository='https://github.com/%s/opencv.git' % (self.username),
            repository='%sopencv.git' % constants.URL_GIT_BASE,
            branch=pr.branch))

        if str(pr.info.get('main', None)) == '1':
            sourcestamps.append(dict(
                codebase='opencv_merge',
                repository='https://github.com/%s/%s.git' % (pr.head_user, 'opencv'),
                branch=main_branch_name,
                revision=main_branch_name))

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
                branch=extra_branch_name,
                revision=extra_branch_name))

        defer.returnValue(True)


context = GitHubContext()
