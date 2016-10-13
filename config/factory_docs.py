import os

from twisted.internet import defer

from buildbot.steps.master import MasterShellCommand
from buildbot.steps.shell import ShellCommand
from buildbot.steps.slave import MakeDirectory
from buildbot.steps.transfer import DirectoryUpload
from buildbot.process.properties import Interpolate, renderer

from build_utils import *
from factory_common import CommonFactory as BaseFactory
from command_check_size import CheckSize


def getRev(repo):
    @renderer
    def getRevInternal(props):
        rev = props.getProperty('revision')
        if not rev:
            rev = props.getProperty('got_revision')
            if isinstance(rev, dict):
                rev = rev[repo]
        if rev is None:
            rev = 'HEAD~10'
        return rev
    return getRevInternal


def getWhitespaceCheckFilter(repo):
    if repo == 'opencv_contrib':
        return ['*.cpp', '*.hpp', '*.c', '*.h',
                '*.py', '*.java',
                '*.txt', '*.md', '*.markdown', '*.bib',
                '*.sh', '*.cmake', '*.txt']
    return []


class Docs_factory(BaseFactory):

    def __init__(self, *args, **kwargs):
        useName = kwargs.pop('useName', 'docs')
        dockerImage = kwargs.pop('dockerImage', (None, 'docs'))
        BaseFactory.__init__(self, *args, useName=useName, buildDocs=True, runTests=False, dockerImage=dockerImage, **kwargs)

    def set_cmake_parameters(self):
        BaseFactory.set_cmake_parameters(self)
        self.cmakepars['WITH_IPP'] = 'OFF'  # Don't download ICV package

    def shouldUpload(self):
        return not self.isPrecommit and ((self.branch == 'master' and self.isContrib) or self.branch == '2.4')

    def getCodebasePath(self, codebase):
        res = {
            'opencv': self.SRC_OPENCV,
            'opencv_contrib': self.SRC_OPENCV_CONTRIB,
            'opencv_extra': self.SRC_OPENCV_EXT,
        }
        return res[codebase]

    @defer.inlineCallbacks
    def build(self):
        if self.isPrecommit:
            yield self.check_whitespaces('opencv')
            if self.isContrib:
                yield self.check_whitespaces('opencv_contrib')

            yield self.check_size('opencv')
            yield self.check_size('opencv_extra')
            if self.isContrib:
                yield self.check_size('opencv_contrib')

        yield self.cmake()
        if isBranch24(self):
            yield self.compile(target='docs', desc='make pdf')
        yield self.compile(target='doxygen', desc='make doxygen', suppressionFile="../%s/doc/disabled_doc_warnings.txt" % self.SRC_OPENCV)

    @defer.inlineCallbacks
    def after_tests_steps(self):
        if not self.isPrecommit:
            # only 2.4 branch have separate 'html' docs
            if self.branch == '2.4':
                yield self.compile(target='html_docs', desc='make html')
            # pack and upload to local release folder
            yield self.pack_docs()
            yield self.upload_release()
            # upload to docs.opencv.org
            if self.shouldUpload():
                yield self.upload_docs()
        else:
            targetPath = 'pr' if not self.isContrib else 'pr_contrib'
            targetPath = os.path.join(targetPath, str(self.getProperty('pullrequest', default='latest')))
            targetPath = os.path.join(targetPath, 'docs')
            targetDirectory = os.path.join(getExportDirectory(), targetPath)
            if os.path.exists(targetDirectory):
                step = \
                    MasterShellCommand(
                        name='cleanup previous docs dir', description='', descriptionDone='',
                        path=getExportDirectory(),
                        command='rm -rf %s' % (targetDirectory),
                        env={},
                        hideStepIf=hideStepIfSuccessSkipFn)
                yield self.processStep(step)
            step = \
                DirectoryUpload(
                    slavesrc='build/doc/doxygen/html',
                    masterdest=targetDirectory,
                    name='upload docs', description='', descriptionDone=''
                    )
            yield self.processStep(step)
            yield step.addURL('preview', 'export/' + targetPath)

    @defer.inlineCallbacks
    def upload_docs(self):
        path = getUploadPathTemplate()
        desc = 'upload'
        step = \
            MasterShellCommand(
                name = desc, description = desc, descriptionDone = desc,
                path = Interpolate(getExportDirectory() + path),
                env = {},
                command=[getDocUploadScript(), self.branch])
        yield self.processStep(step)

    @defer.inlineCallbacks
    def pack_docs(self):
        step = ShellCommand(
                name = "pack docs",
                workdir = "build",
                command = ["python", getDocPackScript(self.osType), "doc", "release"])
        yield self.processStep(step)

    @defer.inlineCallbacks
    def check_whitespaces(self, codebase):
        desc = 'whitespace %s' % codebase
        step = ShellCommand(
            name=desc, description=desc, descriptionDone=desc,
            command=[
                'git', 'diff', '--check', getRev(codebase),
                '--', getWhitespaceCheckFilter(codebase)
            ],
            workdir=self.getCodebasePath(codebase)
        )
        yield self.processStep(step)

    @defer.inlineCallbacks
    def check_size(self, codebase):
        def hasMerge(step):
            merge = step.build.getSourceStamp('%s_merge' % codebase)
            return merge is not None
        desc = 'patch size %s' % codebase
        step = CheckSize(
            codebase,
            self.getCodebasePath(codebase),
            name='patch size %s' % codebase,
            doStepIf=hasMerge,
            hideStepIf=lambda r, _: r == SKIPPED,
            warnOnWarnings=True,
            haltOnFailure=False,
        )
        yield self.processStep(step)

    @defer.inlineCallbacks
    def determineTests(self):
        yield None

    @defer.inlineCallbacks
    def testAll(self):
        yield None
