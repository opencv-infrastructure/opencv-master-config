from buildbot.process.factory import BuildFactory
from buildbot.process.buildstep import BuildStep
from buildbot.steps.source.git import Git
from buildbot.steps.trigger import Trigger
from buildbot.steps.shell import *
from buildbot.steps.slave import *
from buildbot.steps.master import *
from buildbot.steps.transfer import *
from buildbot.process.properties import Interpolate, Property, renderer

from twisted.internet import defer

import re

import constants
from factory_common import CommonFactory as BaseFactory
from factory_common import getDropRoot

from build_utils import OSType
from build_utils import WinCompiler

BLOCK_SIZE=512*1024

def getDirectroryForSlaveDrop(props):
    directory = getDropRoot() + 'winpack/'
    directory += props.getProperty('timestamp', 'unknown_timestamp')
    all_got_revisions = props.getProperty('got_revision', {})
    if 'opencv' in all_got_revisions:
        directory += '-' + all_got_revisions['opencv']
    else:
        directory += '-unknown-revision'
    directory += '/'
    return directory


def getMetaArchiveWithSlaveDrop(props, masterPath=True):
    name = getDropRoot(masterPath) + 'winpack_temporary/'
    name += props.getProperty('timestamp', 'unknown_timestamp')
    all_got_revisions = props.getProperty('got_revision', {})
    if 'opencv' in all_got_revisions:
        name += '-' + all_got_revisions['opencv']
    else:
        name += '-unknown-revision'
    name += '.7z'
    return name


def getDirectoryForWinPack(props, masterPath=True):
    name = getDropRoot(masterPath) + 'winpack_installer/'
    name += props.getProperty('timestamp', 'unknown_timestamp')
    all_got_revisions = props.getProperty('got_revision', {})
    if 'opencv' in all_got_revisions:
        name += '-' + all_got_revisions['opencv']
    else:
        name += '-unknown-revision'
    name += '/'
    return name


def getNameForWinPackDrop(props):
    branch = props.getProperty('branch', 'unknown')
    name = 'opencv-%s-winpack.exe' % branch
    return name


'''
Builder (one per configuration: x64/x86 vc12/vc14 shared/static)
Build debug and release code and save results on server
'''
class WinPackBuild(BaseFactory):

    def __init__(self, *args, **kwargs):
        useName = kwargs.pop('useName', 'winpack-build')
        buildWithContrib = kwargs.pop('buildWithContrib', False)
        BaseFactory.__init__(self, *args, isPrecommit=False,
                             buildWithContrib=buildWithContrib, buildExamples=False, runTests=False,
                             useName=useName, **kwargs)

    @defer.inlineCallbacks
    def checkout_sources(self):
        yield BaseFactory.checkout_sources(self, process_extra=False)


    @defer.inlineCallbacks
    def build(self):
        yield self.cmake()
        yield self.compile(config='release', target='install', useClean=False)
        yield self.compile(config='debug', target='install', useClean=False)


    @defer.inlineCallbacks
    def after_build_steps(self):
        yield self.packInstall()
        yield self.uploadOnMaster()


    def disabled_getNameSuffix(self):
        suffix = BaseFactory.getNameSuffix(self)
        return suffix + ("-shared" if self.buildShared else "-static")


    def getSlaves(self):
        if self.osType == OSType.WINDOWS:
            if self.compiler in ['vc10', 'vc11']:
                return []
            if self.compiler == 'vc14':
                return ['windows-1', 'windows-2']
        else:
            return ['linux-1', 'linux-2']
        raise Exception('Invalid configuration')


    def set_cmake_parameters(self):
        BaseFactory.set_cmake_parameters(self)
        self.cmakepars['BUILD_TESTS'] = 'OFF'
        self.cmakepars['BUILD_PERF_TESTS'] = 'OFF'
        self.cmakepars['BUILD_DOCS'] = 'OFF'
        self.cmakepars['BUILD_opencv_java'] = 'OFF'
        if self.branch == '2.4':
            self.cmakepars['BUILD_opencv_python'] = 'OFF'
        else:
            self.cmakepars['BUILD_opencv_python2'] = 'OFF'
            self.cmakepars['BUILD_opencv_python3'] = 'OFF'
        self.cmakepars['WITH_OPENCL'] = 'ON'
        self.cmakepars['WITH_CUDA'] = 'OFF'
        self.cmakepars['ENABLE_SSE'] = 'ON'
        self.cmakepars['ENABLE_SSE2'] = 'ON'
        self.cmakepars['WITH_TBB'] = 'OFF'
        self.cmakepars['CMAKE_INSTALL_PREFIX'] = Interpolate('%(prop:workdir)s/install')
        self.cmakepars['INSTALL_CREATE_DISTRIB'] = 'ON'


    @defer.inlineCallbacks
    def packInstall(self):
        command = self.envCmd
        command += '7z' if self.osType == OSType.WINDOWS else '7za'
        command += ' a -bd -t7z -y -mx7 ../build/install.7z ./'

        step = ShellCommand(workdir='install', description='pack', descriptionDone='pack',
                            descriptionSuffix='shared' if self.buildShared else 'static',
                            command=command, env=self.env)
        yield self.processStep(step)


    @defer.inlineCallbacks
    def uploadOnMaster(self):
        dst = getDirectroryForSlaveDrop(self)
        dst += 'winpack-install-%s-%s%s%s-build%05d.7z' % (
            self.branchSafeName,
            self.name(),
            self.getPlatformSuffix(),
            self.getNameSuffix(),
            self.getProperty('buildnumber'))

        step = FileUpload(workdir='build', slavesrc='install.7z', masterdest=dst, blocksize=BLOCK_SIZE)
        yield self.processStep(step)


'''
Builder for bindings
'''
class WinPackBindings(WinPackBuild):

    def __init__(self, *args, **kwargs):
        WinPackBuild.__init__(self, *args, useName='winpack-bindings', **kwargs)
        assert not self.buildShared

    @defer.inlineCallbacks
    def build(self):
        yield self.cmake()
        yield self.compile(config='release', target='modules/java/install', desc='java', useClean=False)
        if self.branch == '2.4':
            yield self.compile(config='release', target='modules/python/install', desc='python', useClean=False)
        else:
            yield self.compile(config='release', target='modules/python2/install', desc='python', useClean=False)


    def set_cmake_parameters(self):
        WinPackBuild.set_cmake_parameters(self)
        self.cmakepars['BUILD_SHARED_LIBS'] = 'OFF'
        self.cmakepars['BUILD_DOCS'] = 'OFF'
        self.cmakepars['BUILD_opencv_java'] = 'ON'
        if self.branch == '2.4':
            self.cmakepars['BUILD_opencv_python'] = 'ON'
        else:
            self.cmakepars['BUILD_opencv_python2'] = 'ON'
            self.cmakepars['BUILD_opencv_python3'] = 'OFF'


'''
Builder for docs
'''
class WinPackDocs(WinPackBuild):

    def __init__(self, *args, **kwargs):
        WinPackBuild.__init__(self, *args, useName='winpack-docs', dockerImage=(None, 'docs'), **kwargs)
        assert self.branch == '2.4' # Doxygen HTML documentation is not packaged
        assert self.osType == OSType.LINUX
        assert self.is64

    def getSlaves(self):
        return ['linux-1', 'linux-2']

    @defer.inlineCallbacks
    def build(self):
        yield self.cmake()
        yield self.compile(config='release', target='install_docs', desc='install docs', useClean=False, runParallel=False)

    def set_cmake_parameters(self):
        WinPackBuild.set_cmake_parameters(self)
        self.cmakepars['BUILD_DOCS'] = 'ON'
        self.cmakepars['OPENCV_DOC_INSTALL_PATH'] = 'doc'


class WinPackTest(WinPackBuild):

    def __init__(self, *args, **kwargs):
        WinPackBuild.__init__(self, *args, useName='winpack-test', **kwargs)


    @defer.inlineCallbacks
    def checkout_sources(self):
        # TODO Buildbot has bug with transferring of large files
        yield self.downloadWinPackMaster()
        yield self.unpackDistrib()


    @defer.inlineCallbacks
    def build(self):
        yield self.cmake(builddir='build/samples_build', cmakedir='../distrib/opencv/sources/samples')
        yield self.compile(builddir='build/samples_build', config='release', target=None, useClean=False)
        yield self.compile(builddir='build/samples_build', config='debug', target=None, useClean=False)


    def set_cmake_parameters(self):
        WinPackBuild.set_cmake_parameters(self)
        self.cmakepars = {}
        self.cmakepars['BUILD_SHARED_LIBS'] = 'ON' if self.buildShared else 'OFF'
        self.cmakepars['OpenCV_DIR'] = Interpolate('%(prop:workdir)s/build/distrib/opencv/build')


    @defer.inlineCallbacks
    def downloadWinPackMaster(self):
        src = getDirectoryForWinPack(self)
        src += getNameForWinPackDrop(self)
        step = FileDownload(workdir='build', mastersrc=src, slavedest='distrib.7z.exe', blocksize=BLOCK_SIZE)
        yield self.processStep(step)


    @defer.inlineCallbacks
    def unpackDistrib(self):
        step = FileDownload(workdir='build',
            mastersrc='winpack/winpack_unpack.cmd', slavedest='winpack_unpack.cmd', hideStepIf=lambda result, s: result == SUCCESS)
        yield self.processStep(step)

        cmd = self.envCmd + 'winpack_unpack.cmd'
        step = ShellCommand(command=cmd, workdir='build',
            description='unpack WinPack', descriptionDone='unpack WinPack', env=self.env)
        yield self.processStep(step)



class PackController(BaseFactory):

    def __init__(self, *args, **kwargs):
        BaseFactory.__init__(self, compiler=None, buildWithContrib=False, runTests=False, is64=None, **kwargs)


    def getSlaves(self):
        return ['windows-pack']


class WinPackController(PackController):

    def __init__(self, *args, **kwargs):
        self.buildTriggerName = kwargs.pop('buildTriggerName', None)
        self.createTriggerName = kwargs.pop('createTriggerName', None)
        assert not self.buildTriggerName is None
        assert not self.createTriggerName is None
        PackController.__init__(self, **kwargs)


    def name(self):
        return 'winpack_controller'


    @defer.inlineCallbacks
    def checkout_sources(self):
        yield PackController.checkout_sources(self, process_extra=False)


    @defer.inlineCallbacks
    def build(self):
        yield self.triggerBuilds()
        if self.bb_build.result == SUCCESS:
            yield self.triggerCreate()


    @defer.inlineCallbacks
    def triggerBuilds(self):
        step = \
            Trigger(
                name='Run per-configuration builds',
                schedulerNames=[self.buildTriggerName], updateSourceStamp=True, waitForFinish=True,
                set_properties={'timestamp' : Property('timestamp')}
            )
        yield self.processStep(step)


    @defer.inlineCallbacks
    def triggerCreate(self):
        step = \
            Trigger(
                name='Run package creation builds',
                schedulerNames=[self.createTriggerName], updateSourceStamp=True, waitForFinish=False,
                set_properties={'timestamp' : Property('timestamp')},
            )
        yield self.processStep(step)



class WinPackCreate(PackController):

    def __init__(self, *args, **kwargs):
        self.testsTriggerName = kwargs.pop('testsTriggerName', None)
        self.completionTriggerName = kwargs.pop('completionTriggerName', None)
        assert not self.testsTriggerName is None
        assert not self.completionTriggerName is None
        PackController.__init__(self, **kwargs)


    def name(self):
        return 'winpack_controller-create'


    @defer.inlineCallbacks
    def checkout_sources(self):
        yield PackController.checkout_sources(self, process_extra=False)


    @defer.inlineCallbacks
    def build(self):
        yield self.concatConfigurationPacks()
        yield self.buildPackage()
        yield self.uploadPackage()


    @defer.inlineCallbacks
    def after_build_steps(self):
        yield self.triggerTestsBuilds()
        yield self.triggerUploadBuilds()


    @defer.inlineCallbacks
    def concatConfigurationPacks(self):
        directory = getDirectroryForSlaveDrop(self)
        metaname = getMetaArchiveWithSlaveDrop(self)
        command = './winpack/pack_slave_builds.sh %s %s' % (directory, metaname)

        step = \
            MasterShellCommand(
                command=command, description='concat slave packs',
                descriptionDone='concat slave packs', hideStepIf=lambda result, s: result == SUCCESS)
        yield self.processStep(step)

        src = getDirectoryForWinPack(self)
        src += getNameForWinPackDrop(self)
        step = FileDownload(workdir='build', mastersrc=metaname, slavedest='metapack.7z', blocksize=BLOCK_SIZE)
        yield self.processStep(step)


    @defer.inlineCallbacks
    def buildPackage(self):
        step = \
            FileDownload(workdir='build', mastersrc='winpack/winpack_create-%s.cmd' % self.branch, slavedest='winpack_create.cmd',
                hideStepIf=lambda result, s: result == SUCCESS)
        yield self.processStep(step)

        step = \
            FileDownload(workdir='build',
                mastersrc='winpack/7z_opencv.sfx', slavedest='7z_opencv.sfx',
                hideStepIf=lambda result, s: result == SUCCESS)
        yield self.processStep(step)

        cmd = self.envCmd + 'winpack_create.cmd'

        step = \
            ShellCommand(command=cmd, workdir='build',
                description='build WinPack', descriptionDone='build WinPack', env=self.env)
        yield self.processStep(step)


    @defer.inlineCallbacks
    def uploadPackage(self):
        dst = getDirectoryForWinPack(self)
        dst += getNameForWinPackDrop(self)

        step = FileUpload(workdir='build', slavesrc='distrib.7z.exe', masterdest=dst, mode=0755, blocksize=BLOCK_SIZE)
        yield self.processStep(step)


    @defer.inlineCallbacks
    def triggerTestsBuilds(self):
        step = \
            Trigger(
                name='Run tests',
                schedulerNames=[self.testsTriggerName],
                updateSourceStamp=True, waitForFinish=True,
                set_properties={'timestamp' : Property('timestamp'),
                                'got_revision' : Property('got_revision')},
            )
        yield self.processStep(step)


    @defer.inlineCallbacks
    def triggerUploadBuilds(self):
        step = \
            Trigger(name='Run upload',
                schedulerNames=[self.completionTriggerName],
                updateSourceStamp=True, waitForFinish=False,
                set_properties={'timestamp' : Property('timestamp'),
                                'got_revision' : Property('got_revision')},
            )
        yield self.processStep(step)


class WinPackUpload(PackController):

    def __init__(self, *args, **kwargs):
        self.perfTestsTriggerName = kwargs.pop('perfTestsTriggerName', None)
        #assert not self.perfTestsTriggerName is None
        PackController.__init__(self, **kwargs)


    def name(self):
        return 'winpack_controller-upload'


    @defer.inlineCallbacks
    def build(self):
        if self.perfTestsTriggerName is None:
            return
        step = \
            Trigger(
                name='Run perf tests',
                schedulerNames=[self.perfTestsTriggerName],
                updateSourceStamp=True, waitForFinish=False,
                set_properties={'timestamp' : Property('timestamp'),
                                'got_revision' : Property('got_revision')},
            )
        yield self.processStep(step)
