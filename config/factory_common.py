import datetime
import os
import re

from twisted.internet import defer

from buildbot.config import BuilderConfig
from buildbot.process.build import Build
from buildbot.process.buildstep import BuildStep
from buildbot.process.factory import BuildFactory
from buildbot.process.properties import Interpolate, renderer
from buildbot.sourcestamp import SourceStamp
from buildbot.status.results import SUCCESS
from buildbot.steps.master import MasterShellCommand
from buildbot.steps.shell import ShellCommand, Compile
from buildbot.steps.slave import RemoveDirectory, MakeDirectory
from buildbot.steps.source.git import Git
from buildbot.steps.transfer import FileUpload, DirectoryUpload


from command_test_cpp import CommandTestCPP
from command_test_java import CommandTestJava
from command_test_py import CommandTestPy

from builder_newstyle import BuilderNewStyle

from build_utils import *
from constants import PLATFORM_ANY, PLATFORM_DEFAULT, PLATFORM_SKYLAKE, PLATFORM_SKYLAKE_X

from buildprops_observer import BuildPropertiesObserver

# for separate 'python2' and 'pyhton3' tests
def isPythonTest(t):
    return t.startswith('python')


def getResultFileNameRenderer(testPrefix, test, testSuffix, fileSuffix='xml'):
    @renderer
    def resultFileName(props):
        name = props['timestamp']
        rev = props.getProperty('revision')
        if not rev:
            rev = props.getProperty('got_revision')
            if isinstance(rev, dict):
                rev = rev['opencv']
        if rev:
            name += '-' + rev[:7]
        else:
            name += '-xxxxxxx'
        build = props.getBuild()
        assert isinstance(build, Build)
        merge_ss = build.getSourceStamp('opencv_merge')
        if merge_ss:
            assert isinstance(merge_ss, SourceStamp)
            patch_rev = merge_ss.asDict().get('revision')
            if patch_rev:
                name += '-%s' % patch_rev[:7]
        name += ' '
        platform = props.getProperty('platform')
        if platform:
            name += platform + '-'
        name += testPrefix + '_' + test + testSuffix
        pullrequest = props.getProperty('pullrequest')
        if pullrequest:
            branch = props.getProperty('branch')
            mangled_branch = branch.replace(r'.', '_')
            name += ' pr%s %s_' % (pullrequest, mangled_branch)
        else:
            name += ' '
        name += props['buildername'] + '_' + ('%05d' % props['buildnumber']);
        if fileSuffix:
            name += '.' + fileSuffix
        return name
    return resultFileName

class CommonFactory(BuilderNewStyle):

    SRC_OPENCV = 'opencv'
    SRC_OPENCV_EXT = 'opencv_extra'
    SRC_OPENCV_CONTRIB = 'opencv_contrib'

    plainRunName = ''

    def __repr__(self):
        d = self.__dict__
        name = '?'
        try:
            name = self.getName()
        except:
            pass
        return 'Builder: ' + name + \
            ' branch=' + str(d.get('branch', '?')) + \
            ' useName=' + str(d.get('useName', '?')) + \
            ' osType=' + str(d.get('osType', '?')) + \
            ' compiler=' + str(d.get('compiler', '?')) + \
            ' is64=' + str(d.get('is64', '?')) + \
            ' buildShared=' + str(d.get('buildShared', '?')) + \
            ''

    def __init__(self, **kwargs):
        self.forceSched = kwargs.pop('forceSched', {})
        self.schedulerNightly = kwargs.pop('schedulerNightly', None)  # override settings


        if not hasattr(self, 'useName'):
            self.useName = kwargs.pop('useName', None)
        if not hasattr(self, 'useNamePrefix'):
            self.useNamePrefix = kwargs.pop('useNamePrefix', None)
        if not hasattr(self, 'platform'):
            self.platform = kwargs.pop('platform', None)
        self.branch = kwargs.pop('branch', None)
        self.branchSafeName = self.branch.replace('.', '_') if self.branch else None
        self.osType = kwargs.pop('osType', None)
        self.androidABI = kwargs.pop('androidABI', None)
        assert self.androidABI is None or self.osType == OSType.ANDROID
        self.androidDevice = kwargs.pop('androidDevice', None)
        self.compiler = kwargs.pop('compiler', WinCompiler.VC14 if self.osType == OSType.WINDOWS else None)
        self.is64 = kwargs.pop('is64', True if self.osType in [OSType.WINDOWS, OSType.LINUX] else None)
        self.buildShared = kwargs.pop('buildShared', True)
        assert not (self.buildShared is None)
        self.buildDocs = kwargs.pop('buildDocs', False)
        assert not (self.buildDocs is None)
        self.buildExamples = kwargs.pop('buildExamples', True)
        assert not (self.buildExamples is None)
        self.useSSE = kwargs.pop('useSSE', None) # TODO Rename to useIntrinsics
        self.isDebug = kwargs.pop('isDebug', False)
        self.runPython = kwargs.pop('runPython', self.osType != OSType.ANDROID and not (self.isDebug and self.osType == OSType.WINDOWS))
        self.runTests = kwargs.pop('runTests', True)
        self.testXML = kwargs.pop('testXML', False)
        self.runTestsBigData = kwargs.pop('runTestsBigData', False)
        self.isPrecommit = kwargs.pop('isPrecommit', False)
        self.isPerf = kwargs.pop('isPerf', False)
        self.isContrib = kwargs.pop('isContrib', False)
        self.buildWithContrib = kwargs.pop('buildWithContrib', self.isContrib or self.branch != '2.4')  # Build with opencv_contrib
        self.envCmd = kwargs.pop('envCmd', 'buildenv')
        self.env = kwargs.pop('env', {}).copy()
        self.env['PYTHONDONTWRITEBYTECODE'] = '1'
        self.env['PYTHONUNBUFFERED'] = '1'
        assert type(self.env) is dict
        self.cmake_generator = kwargs.pop('cmake_generator', None)
        self.cmake_toolset = kwargs.pop('cmake_toolset', None) # (builder suffix, toolset value)
        self.cmake_platform = kwargs.pop('cmake_platform', None) # (builder suffix, toolset value)
        self.cmakepars = kwargs.pop('cmake_parameters', {})
        self.r_warning_pattern = re.compile(r'.*warning[: ].*', re.I | re.S)
        self.suppressions = None
        self.buildImage = kwargs.pop('buildImage', kwargs.pop('dockerImage', None))

        BuilderNewStyle.__init__(self, **kwargs)

        if self.useSlave is None:
            self.useSlave = []
            if self.platform in [PLATFORM_DEFAULT, PLATFORM_ANY, PLATFORM_SKYLAKE]:
                if self.osType == OSType.LINUX:
                    if self.is64 is None or self.is64:
                        self.useSlave += ['linux-1', 'linux-2', 'linux-4']
                        #if not self.isPrecommit:
                        #    self.useSlave = ['linux-1']
                    else:
                        self.useSlave += ['linux-1', 'linux-4']
                elif self.osType == OSType.WINDOWS:
                    self.useSlave += ['windows-1', 'windows-2'] if self.compiler != 'vc15' else ['windows-1']
                elif self.osType == OSType.MACOSX:
                    self.useSlave += ['macosx-1', 'macosx-2']
                    #if not self.isPrecommit:
                    #    self.useSlave = ['macosx-1']
                elif self.osType == OSType.ANDROID:
                    self.useSlave += ['linux-4']
                    if self.branch != 'master':
                        self.useSlave += ['linux-1', 'linux-2']
            if self.platform in [PLATFORM_SKYLAKE_X, PLATFORM_ANY]:
                if self.osType == OSType.LINUX:
                    if self.is64 is None or self.is64:
                        self.useSlave += ['linux-3']
                        self.useSlave += ['linux-5']
            if self.useSlave == []:
                self.useSlave = None

        if self.isPrecommit:
            self.env['BUILD_PRECOMMIT'] = '1'
        elif self.isDebug:
            self.cmakepars['ENABLE_CCACHE'] = 'OFF'


    def onNewBuild(self):
        BuilderNewStyle.onNewBuild(self)
        self.env = self.env.copy()
        self.cmakepars = self.cmakepars.copy()

    @defer.inlineCallbacks
    def runPrepare(self):
        yield BuilderNewStyle.runPrepare(self)

        self.env['BUILD_BRANCH'] = self.getProperty('branch', default='master')

        self.buildWithContrib = self.buildWithContrib and not isBranch24(self)  # precommit with 2.4 target

        if self.getProperty('build_contrib', default=None):
            self.buildWithContrib = self.getProperty('build_contrib', default=None) in ['ON', '1', 'TRUE', 'True']

        self.compiler = self.getProperty('build_compiler', default=self.compiler)
        if self.getProperty('build_platform', default=None):
            self.cmake_platform = (None, str(self.getProperty('build_platform', default=None)))

        if self.buildImage is None:
            if self.osType == OSType.LINUX:
                default_docker = (None, 'ubuntu:14.04') if not isBranchMaster(self) else (None, 'ubuntu:16.04')
                self.buildImage = default_docker if not (self.is64 is False) else (None, 'ubuntu32:16.04')
            elif self.osType == OSType.ANDROID:
                self.buildImage = (None, 'android:14.04') if not isBranchMaster(self) else (None, 'android-gradle')
            else:
                # not applicable
                pass

        if self.isPrecommit:
            prefix = self.bb_requests[0].properties.getProperty('branch', default=None)
            if prefix and prefix != 'master':
                self.SRC_OPENCV = prefix + '/' + self.SRC_OPENCV
                self.SRC_OPENCV_EXT = prefix + '/' + self.SRC_OPENCV_EXT
                self.SRC_OPENCV_CONTRIB = prefix + '/' + self.SRC_OPENCV_CONTRIB
        buildImage = self.bb_requests[0].properties.getProperty('build_image', default=None)
        if buildImage:
            self.buildImage = (None, buildImage)
        if self.buildImage:
            buildImageName = str(self.buildImage[1] if isinstance(self.buildImage, (list, tuple)) else self.buildImage)
            buildImageName = re.sub(r'[^\w\-_0-9\:\.]|\.\.', '', buildImageName)
            assert len(buildImageName) > 0
            assert buildImageName.find('..') == -1, buildImageName
            assert buildImageName.find('/') == -1, buildImageName
            assert buildImageName.find('\\') == -1, buildImageName
            self.env['BUILD_IMAGE']='opencv-' + buildImageName

        if self.osType == OSType.ANDROID and self.suppressions is None:
            self.suppressions = [[None, re.compile(r'\[apkbuilder\]'), None, None]]  # warning: "The JKS keystore uses a proprietary format"
        if self.osType == OSType.MACOSX and self.suppressions is None:
            # ld: warning: text-based stub file /System/Library/Frameworks//OpenCL.framework/OpenCL.tbd
            # and library file /System/Library/Frameworks//OpenCL.framework/OpenCL are out of sync. Falling back to library file for linking.
            self.suppressions = [[None, re.compile(r'text-based stub file'), None, None]]

        bigData = self.getProperty('test_bigdata', None)
        if bigData is not None:
            self.runTestsBigData = bool(bigData)

        if self.runTestsBigData:
            self.setProperty('parallel_tests', 1)  # avoid running of OOM killer
            self.env['BUILD_BIGDATA'] = '1'  # create docker container (Linux) with relaxed memory limits

        disable_ipp_prop = self.getProperty('disable_ipp', default=None)
        if disable_ipp_prop in ['ON', '1', 'TRUE', 'True']:
            self.env['OPENCV_IPP'] = 'disabled'


    def initializePostProcess(self):
        platform = self.cmake_platform[1] if self.cmake_platform else None

        ci_build_arch_prop = self.getProperty('ci-build_arch', default=None)
        if ci_build_arch_prop:
            if 'BUILD_ARCH' in self.env:
                del self.env['BUILD_ARCH']
            self.cmake_platform = None
            platform = str(ci_build_arch_prop)
        ci_build_compiler_prop = self.getProperty('ci-build_compiler', default=None)
        if ci_build_compiler_prop:
            self.compiler = str(ci_build_compiler_prop)

        if self.osType == OSType.WINDOWS and self.compiler is not None:
            cmake_options = WinCompiler.getCMakeOptions(self.compiler, platform, self.is64)
            if self.cmake_generator is None and cmake_options[0]:
                self.cmake_generator = cmake_options[0]
            if self.cmake_platform is None and cmake_options[1]:
                self.cmake_platform = cmake_options[1]

        if self.osType != OSType.ANDROID:
            if not 'BUILD_ARCH' in self.env:
                if self.cmake_platform:
                    self.env['BUILD_ARCH'] = self.cmake_platform[1]
                elif platform:
                    self.env['BUILD_ARCH'] = platform
                elif self.is64 is not None:
                    self.env['BUILD_ARCH'] = 'x64' if self.is64 else 'x86'
            if (not 'BUILD_COMPILER' in self.env) and (self.compiler is not None):
                self.env['BUILD_COMPILER'] = self.compiler


    def getTags(self):
        res = list(BuilderNewStyle.getTags(self))

        # takes one of 'master', 'master-contrib', '2.4'
        if self.branch == '2.4':
            second = '2.4'
        elif self.branch == '3.4':
            second = '3.4'
        else:
            second = 'master'

        if self.isContrib and self.branch != '2.4':
            second += '-contrib'

        third = 'main'
        if self.isContrib:
            third = 'contrib'

        res.append(third)
        if self.isPrecommit:
            res.append('precommit')
            res.append('precommit-' + third)
        else:
            res.append('branch-' + self.branch)
            res.append('scheduled')
            res.append('scheduled-' + second)
        res.append('os-' + self.osType)
        res.append('platform-' + self.platform)
        return list(set(res))


    def getRunPy(self, full = False):
        '''
        full is True - return list with options suitable for shell command
        full is False - return string with path to script
        '''
        f = '../%s/modules/ts/misc/run.py' % self.SRC_OPENCV
        if not full:
            return f
        else:
            run_py = [f]
            if self.isDebug:
                run_py.append('--configuration=Debug')
                if isNotBranch24(self):
                    run_py.append('--test_tag_skip=size_hd')
            if self.androidABI:
                run_py += ['--android_propagate_opencv_env', '--android_test_data_path /data/local/tmp/opencv/testdata/']
                if self.androidDevice:
                    run_py += ['--serial', self.androidDevice]
            return run_py

    def getTestBlacklist(self, isPerf=False):
        '''
        list of tests to skip, due to some problems:
        - java: should be fixed
        - tracking: too long (> 24 hrs), should be optimized
        - viz: needs OpenGL windows
        - shape: should be fixed
        - gpu: not tested yet
        '''
        if isBranch24(self):
            return ["gpu"]
        else:
            return ["viz", "shape"] + (["stereo", "tracking", "imgcodecs"] if isPerf else ["flann"])

    def getTestMaxTime(self, isPerf):
        ''' total timeout for test execution, seconds '''
        maxtime_prop = self.getProperty('test_maxtime', default=None)
        if maxtime_prop:
            return int(maxtime_prop)

        if self.isPrecommit:
            return 40 * 60
        elif isPerf:
            return 120 * 60
        else:
            return 60 * 60

    def getTestTimeout(self):
        ''' timeout for test execution without output, seconds '''
        timeout_prop = self.getProperty('test_timeout', default=None)
        if timeout_prop:
            return int(timeout_prop)

        if self.isPrecommit and self.isDebug != True:
            return 3 * 60
        else:
            return 10 * 60

    @defer.inlineCallbacks
    def run(self):
        yield self.initialize()
        yield self.cleanup_builddir()
        yield self.checkout_sources()
        stages_str = self.getProperty('ci-stages', default=None)
        if stages_str:
            stages_str = str(stages_str)
            stages = stages_str.split(',')
            for stage in stages:
                if stage == 'upload_release':
                    yield self.upload_release()
                    continue
                env = self.env.copy()
                env['BUILD_STAGE'] = stage
                env['BUILD_SRC_OPENCV'] = '../' + self.SRC_OPENCV
                env['BUILD_SRC_OPENCV_EXTRA'] = '../' + self.SRC_OPENCV_EXT
                env['BUILD_SRC_OPENCV_CONTRIB'] = '../' + self.SRC_OPENCV_CONTRIB
                step = ShellCommand(name=stage, descriptionDone=' ', description=' ',
                        command=self.envCmd + 'echo Stage ' + stage, env=env, workdir='build'
                    )
                yield self.processStep(step)
                if self.bb_build.result != SUCCESS:
                    break
        else:
            yield self.build()
            yield self.after_build_steps()
            if self.runTests and bool(self.getProperty('ci-run_tests', default=True)):
                yield self.determineTests()
                yield self.testAll()
            yield self.after_tests_steps()

        if self.bb_build.result == SUCCESS and self.isPrecommit != True:
            yield self.cleanup_builddir()


    @defer.inlineCallbacks
    def runCleanup(self):
        # TODO Forced cleanup: yield self.cleanup_builddir()
        env = self.env.copy()
        env['BUILD_FINALIZE'] = '1'
        env['BUILD_SRC_OPENCV'] = self.SRC_OPENCV
        env['BUILD_SRC_OPENCV_EXTRA'] = self.SRC_OPENCV_EXT
        env['BUILD_SRC_OPENCV_CONTRIB'] = self.SRC_OPENCV_CONTRIB
        step = ShellCommand(name='finalize', descriptionDone=' ', description=' ',
                command=self.envCmd + 'echo Finalize', env=env, workdir='.',
                alwaysRun=True)
        yield self.processStep(step)
        del env['BUILD_FINALIZE']
        env['BUILD_CLEANUP'] = '1'
        step = ShellCommand(name='cleanup', descriptionDone=' ', description=' ',
                command=self.envCmd + 'echo Cleanup', env=env, workdir='.',
                alwaysRun=False) # skip cleanup on failures for debug purposes
        if self.bb_build.result == SUCCESS and self.isPrecommit != True:
            yield self.processStep(step)


    def getName(self):  # derived classes should implement only name() method
        if self.builderName:
            return self.builderName
        name = self.nameprefix()
        name += self.branchSafeName if not self.isPrecommit else 'precommit'
        if self.isContrib:
            name += '-contrib'
        n = self.name()
        if n and len(n) > 0:
            name += '_' + n
        if self.useSSE == False:
            name += '_noSSE'
        name += self.getPlatformSuffix()
        name += self.getNameSuffix()
        return name


    def getPlatformSuffix(self):
        name = ''
        if self.platform and self.platform not in [PLATFORM_DEFAULT, PLATFORM_ANY]:
            name = '-' + self.platform
        if self.osType:
            name += '-' + OSType.suffix[self.osType]
            if self.osType != OSType.ANDROID:
                name += '' if self.is64 is None else ('64' if self.is64 else '32')
                if self.compiler is not None:
                    name += '-' + self.compiler
            else:
                if self.androidABI:
                    name += '-' + self.androidABI
        return name


    def initConstants(self):
        if self.envCmd is None:
            self.envCmdList = []
            self.envCmd = ''
        else:
            self.envCmdList = [self.envCmd]
            self.envCmd += ' '


    @defer.inlineCallbacks
    def initialize(self):
        builddir = self.getProperty('builddir', default='build_directory').replace('\\', '/')
        self.env['BUILD_DIR_PATH'] = builddir
        self.env['BUILD_DIR'] = os.path.basename(builddir)
        timestamp = datetime.datetime.now()
        timestamp_str = timestamp.strftime('%Y%m%d-%H%M%S')
        prop_name = 'timestamp' if not self.hasProperty('timestamp') else 'my_timestamp'
        self.setProperty(prop_name, timestamp_str, 'Initialize Step')

        # run buildenv with dummy command to remove Git index.lock
        env = self.env.copy()
        env['BUILD_INITIALIZE'] = '1'
        ci_branch = self.getProperty('ci-branch', default=None)
        if ci_branch is None:
            ci_branch = self.getProperty('branch', default=None)
        if ci_branch and not ci_branch.startswith('2.4'):
            self.env['BUILD_CI_BRANCH'] = ci_branch
            env['BUILD_CI_BRANCH'] = ci_branch
            env['BUILD_INIT_CI'] = '1'
            env['BUILD_CI_URL'] = 'git://code.ocv/opencv/opencv-ci.git'
        step = ShellCommand(name='init', descriptionDone=' ', description=' ',
                command=self.envCmd + 'echo Initialize', env=env, workdir='.',
                maxTime=24*60*60, timeout=24*60*60,
                haltOnFailure=True)
        step.addLogObserver('stdio', BuildPropertiesObserver(self))
        yield self.processStep(step)
        self.initializePostProcess()


    @defer.inlineCallbacks
    def checkout_sources(self, process_extra=True, process_contrib=True):
        getDescriptionOptions = {
             'always': True
        }
        step = Git(name='Fetch opencv', repourl=Interpolate('%(src:opencv:repository)s'), workdir=self.SRC_OPENCV,
            haltOnFailure=True, codebase='opencv', getDescription=getDescriptionOptions, mode='full', method='clean')
        yield self.processStep(step)
        if process_extra:
            step = Git(name='Fetch extra', repourl=Interpolate('%(src:opencv_extra:repository)s'), workdir=self.SRC_OPENCV_EXT,
                haltOnFailure=True, codebase='opencv_extra', getDescription=getDescriptionOptions, mode='full', method='clean')
            yield self.processStep(step)
        if process_contrib and self.buildWithContrib:
            step = Git(name='Fetch opencv_contrib', repourl=Interpolate('%(src:opencv_contrib:repository)s'), workdir=self.SRC_OPENCV_CONTRIB,
                haltOnFailure=True, codebase='opencv_contrib', getDescription=getDescriptionOptions, mode='full', method='clean')
            yield self.processStep(step)

        if self.isPrecommit:
            step = getMergeCommand('opencv', self.SRC_OPENCV)
            yield self.processStep(step)
            if process_extra:
                step = getMergeCommand('opencv_extra', self.SRC_OPENCV_EXT)
                yield self.processStep(step)
            if process_contrib and self.buildWithContrib:
                step = getMergeCommand('opencv_contrib', self.SRC_OPENCV_CONTRIB)
                yield self.processStep(step)


    @defer.inlineCallbacks
    def cleanup_builddir(self):
        step = RemoveDirectory(
            dir='install', hideStepIf=lambda result, s: result == SUCCESS,
            haltOnFailure=True)
        yield self.processStep(step)
        step = RemoveDirectory(
            dir='build', hideStepIf=lambda result, s: result == SUCCESS,
            haltOnFailure=True)
        yield self.processStep(step)
        step = MakeDirectory(
            dir='build', hideStepIf=lambda result, s: result == SUCCESS,
            haltOnFailure=True)
        yield self.processStep(step)

    @defer.inlineCallbacks
    def build(self):
        yield self.cmake()
        yield self.compile(config='debug' if self.isDebug else 'release')
        yield self.optional_build_gapi_standalone()

    def set_cmake_parameters(self):
        if self.getProperty('build_shared', default=None) is not None:
            self.cmakepars['BUILD_SHARED_LIBS'] = 'ON' if self.getProperty('build_shared', default=None) in ['ON', '1', 'TRUE', 'True'] else 'OFF'
        else:
            self.cmakepars['BUILD_SHARED_LIBS'] = 'ON' if self.buildShared else 'OFF'
        if self.buildExamples is not None:
            self.cmakepars['BUILD_EXAMPLES'] = Interpolate('%(prop:build_examples:-' + ('ON' if self.buildExamples else 'OFF') + ')s')
        if not self.buildDocs is None:
            self.cmakepars['BUILD_DOCS'] = 'ON' if self.buildDocs else 'OFF'
        self.cmakepars['BUILD_TESTS'] = 'ON'
        self.cmakepars['BUILD_PERF_TESTS'] = 'ON'

        if self.useSSE is None:
            pass  # default
        elif self.useSSE == True:
            if isBranch24(self):
                self.cmakepars['ENABLE_SSE2'] = 'ON'
                self.cmakepars['ENABLE_SSE3'] = 'ON'
        elif self.useSSE == False:
            if isBranch24(self):
                self.cmakepars['ENABLE_SSE2'] = 'OFF'
                self.cmakepars['ENABLE_SSE3'] = 'OFF'
            elif self.isDebug:
                self.cmakepars['CV_DISABLE_OPTIMIZATION'] = 'ON'
                pass

        if self.osType == OSType.ANDROID:
            del self.cmakepars['BUILD_SHARED_LIBS']
            self.cmakepars['CMAKE_TOOLCHAIN_FILE'] = '../%s/platforms/android/android.toolchain.cmake' % self.SRC_OPENCV
            if self.androidABI:
                self.cmakepars['ANDROID_ABI'] = self.androidABI
            if self.androidABI is None or self.androidABI.startswith('arm'):
                self.cmakepars['ANDROID_TOOLCHAIN_NAME'] = 'arm-linux-androideabi-4.8' if not self.is64 else 'aarch64-linux-android-4.9'

        if self.isDebug:
            self.cmakepars['CMAKE_BUILD_TYPE'] = 'Debug'

        if self.osType == OSType.LINUX and isNotBranch24(self):
            self.cmakepars['WITH_OPENNI2'] = 'ON'
            self.cmakepars['WITH_GDAL'] = 'ON'
            self.cmakepars['PYTHON_DEFAULT_EXECUTABLE'] = '/usr/bin/python3'
            self.cmakepars['WITH_GDCM'] = 'ON'

        if self.isPrecommit and isNotBranch24(self) and self.osType == OSType.WINDOWS and hasattr(self, 'buildOpenCL'):
            if self.buildOpenCL:
                self.cmakepars['WITH_DSHOW'] = 'ON'
                self.cmakepars['WITH_VFW'] = 'ON'

        if self.buildWithContrib:
            self.cmakepars['OPENCV_EXTRA_MODULES_PATH'] = self.getProperty('workdir') + '/' + self.SRC_OPENCV_CONTRIB + '/modules'

        if self.isPrecommit and isNotBranch24(self):
            self.cmakepars['OPENCV_ENABLE_NONFREE'] = 'ON'

        if self.getProperty('build_world', default=None):
            self.cmakepars['BUILD_opencv_world'] = 'ON' if self.getProperty('build_world', default=None) in ['ON', '1', 'TRUE', 'True'] else 'OFF'

        if self.getProperty('build_cxxflags', default=None):
            self.cmakepars['CMAKE_CXX_FLAGS'] = '%s' % self.getProperty('build_cxxflags', default='')

        if self.getProperty('build_cpu_baseline', default=None) is not None:
            self.cmakepars['CPU_BASELINE'] = '%s' % self.getProperty('build_cpu_baseline', default='')
        if self.getProperty('build_cpu_dispatch', default=None) is not None:
            self.cmakepars['CPU_DISPATCH'] = '%s' % self.getProperty('build_cpu_dispatch', default='')

        if self.getProperty('build_cxxflags_extra', default=None):
            self.cmakepars['OPENCV_EXTRA_CXX_FLAGS'] = '%s' % self.getProperty('build_cxxflags_extra', default='')

        if self.getProperty('build_tbb', default=None):
            self.cmakepars['BUILD_TBB'] = 'ON' if self.getProperty('build_tbb', default=None) in ['ON', '1', 'TRUE', 'True'] else 'OFF'

        if self.getProperty('with_tbb', default=None):
            self.cmakepars['WITH_TBB'] = 'ON' if self.getProperty('with_tbb', default=None) in ['ON', '1', 'TRUE', 'True'] else 'OFF'

        build_pkgconfig = self.getProperty('build_pkgconfig', default=None)
        if build_pkgconfig is not None:
            self.cmakepars['OPENCV_GENERATE_PKGCONFIG'] = 'ON' if bool(build_pkgconfig) else 'OFF'

        if self.osType == OSType.WINDOWS:
            self.cmakepars['OPENCV_PYTHON_INSTALL_PATH'] = 'python'


    @defer.inlineCallbacks
    def cmake(self, builddir='build', cmakedir=None, desc='cmake', cmakepars=None):
        if cmakedir is None:
            cmakedir = '../' + self.SRC_OPENCV
        if cmakepars is None:
            self.set_cmake_parameters()
            cmakepars_dict = self.cmakepars.copy()
        else:
            cmakepars_dict = cmakepars.copy()
        @renderer
        @defer.inlineCallbacks
        def cmake_command(props):
            cmakepars = {}
            for key, value in cmakepars_dict.items():
                value = yield interpolateParameter(value, props)
                cmakepars[key] = value
            cmakepars = ['-D%s=%s' % (key, value) \
                for key, value in cmakepars.items() if value is not None]

            command = self.envCmdList + ['cmake']
            if self.cmake_generator:
                command += ['-G', self.cmake_generator]
            if self.cmake_toolset:
                command += ['-T', self.cmake_toolset[1]]
            if self.cmake_platform:
                command += ['-A', self.cmake_platform[1]]
            command += cmakepars
            command += [cmakedir]
            defer.returnValue(command)

        step = Compile(command=cmake_command, env=self.env,
            workdir=builddir, name=desc, haltOnFailure=True,
            descriptionDone=desc, description=desc,
            logfiles=dict(cache='CMakeCache.txt', vars='CMakeVars.txt', CMakeOutput='CMakeFiles/CMakeOutput.log', CMakeError='CMakeFiles/CMakeError.log'),
            warningPattern=self.r_warning_pattern, warnOnWarnings=True)
        yield self.processStep(step)


    @defer.inlineCallbacks
    def compile(self, builddir='build', config='release', target=None, useClean=False, desc=None, doStepIf=True,
                warningPattern=None, suppressionFile=None, suppressions=None,
                runParallel=True, **kwargs):
        @renderer
        def compileCommand(props):
            command = self.envCmdList + ['cmake', '--build', '.', '--config', config]
            if not target is None:
                command += ['--target', target]
            if useClean:
                command += ['--clean-first']
            if runParallel:
                cpus = props.getProperty('CPUs')
                if not cpus:
                    cpus = 1
                if self.osType == OSType.WINDOWS or (self.compiler and self.compiler.startswith('vc')):
                    command += ['--', '/maxcpucount:%s' % cpus, '/consoleloggerparameters:NoSummary']
                else:
                    command += ['--', '-j%s' % cpus]
            return command

        if desc is None:
            desc = 'compile %s' % config
        if warningPattern is None:
            warningPattern = self.r_warning_pattern
        step = \
            Compile(command=compileCommand, workdir=builddir, env=self.env,
                    name=desc, descriptionDone=desc, description=desc, doStepIf=doStepIf,
                    warningPattern=warningPattern,
                    warnOnWarnings=True, haltOnFailure=True,
                    suppressionFile=suppressionFile, **kwargs)
        if suppressions or self.suppressions:
            step.addSuppression((suppressions or []) + (self.suppressions or []))
        yield self.processStep(step)

    def getModuleAccuracyTestFilter(self, module):
        return None

    def getModulePerfTestFilter(self, module):
        return None

    def getModuleAccuracyTestCommandPrefix(self, module):
        if module == 'highgui' and self.osType == OSType.LINUX:
            return 'xvfb-run -a '
        return None

    def getModulePerfTestCommandPrefix(self, module):
        return None

    @defer.inlineCallbacks
    def addTestsPrepareStage(self):
        if hasattr(self, 'prepareStageAdded'):
            return
        self.prepareStageAdded = True
        if self.androidABI:
            if self.androidDevice:
                desc = 'adb connect'
                step = ShellCommand(
                            command=self.envCmd + 'adb connect %s' % self.androidDevice,
                            env=self.env,
                            name=desc, descriptionDone=desc, description=desc,
                            warnOnWarnings=True, haltOnFailure=True)
                yield self.processStep(step)
            desc = 'adb load extra data'
            step = ShellCommand(
                        # command=self.envCmd + 'adb%s push testdata /data/local/tmp/opencv/testdata' % (' -s %s' % self.androidDevice if self.androidDevice else ''),
                        command=self.envCmd + 'find ./testdata/ -exec adb%s push {} /data/local/tmp/opencv/{} \;' % (' -s %s' % self.androidDevice if self.androidDevice else ''),
                        workdir=self.SRC_OPENCV_EXT, env=self.env,
                        name=desc, descriptionDone=desc, description=desc,
                        warnOnWarnings=True, haltOnFailure=True)
            yield self.processStep(step)


    @defer.inlineCallbacks
    def addTestSteps(self, isPerf, listOfTests = [], builddir='build', testFilter=Interpolate('%(prop:test_filter)s'), performance_samples=[], implementation=None,
                     testSuffix='', uploadDir=None, haltOnFailure=True, doStepIf=True):
        steps = []

        if self.androidABI and self.androidDevice is None:
            # No tests without device
            defer.returnValue(steps)

        yield self.addTestsPrepareStage()

        performance_samples = list(performance_samples)
        if isPerf:
            if implementation:
                performance_samples.append('--perf_impl=%s' % implementation)

        buildDesc = ''
        if builddir != 'build':
            buildDesc = '-%s' % builddir

        run_py = self.getRunPy(full=True)

        common_env = self.env.copy()
        common_env['OPENCV_TEST_DATA_PATH'] = Interpolate('%(prop:workdir)s/' + self.SRC_OPENCV_EXT + '/testdata')
        if isPerf and self.isPerf and (not '--check' in performance_samples):
            common_env['BUILDBOT_COMMAND_EXCLUSIVE'] = '1'
        if self.runTestsBigData:
            common_env['BUILDBOT_COMMAND_EXCLUSIVE'] = '1'

        testPrefix = 'perf' if isPerf else 'test';
        for test in listOfTests:
            if self.runTestsBigData:
                if test == 'java' or isPythonTest(test):
                    continue

            env = common_env.copy()
            step = None
            hname = '%s_%s%s%s' % (testPrefix, test, testSuffix, buildDesc)

            resultsFileOnSlave = 'results_%s_%s%s.xml' % (testPrefix, test, testSuffix)

            if self.androidABI:
                if isPythonTest(test) or test == 'java':
                    continue

            if isPythonTest(test):
                lib_sub_dir = '/lib'
                path_sep = ':'
                if test == 'python3':
                    lib_sub_dir += '/python3'
                if self.osType == OSType.WINDOWS:
                    lib_sub_dir += '/Release'
                    path_sep = ';'
                env['PYTHONPATH'] = Interpolate('%(prop:workdir)s/' + builddir + '/python_loader' + path_sep + '%(prop:workdir)s/' + builddir + lib_sub_dir)

            def getCommand(test, _testFilter, resultsFileOnSlave):
                @renderer
                @defer.inlineCallbacks
                def command(props):
                    testFilter = yield interpolateParameter(_testFilter, props)

                    moduleTestCommandPrefix = self.getModuleAccuracyTestCommandPrefix(test) if not isPerf else self.getModulePerfTestCommandPrefix(test)
                    cmd = self.envCmd + (moduleTestCommandPrefix if moduleTestCommandPrefix else '')
                    if not isPythonTest(test):
                        cmd += ('python %s' % " ".join(run_py))
                        moduleTestFilter = self.getModuleAccuracyTestFilter(test) if not isPerf else self.getModulePerfTestFilter(test)
                        if testFilter is not None and testFilter != '':
                            moduleTestFilter = testFilter
                        if self.runTestsBigData:
                            if moduleTestFilter is None or moduleTestFilter == '':
                                moduleTestFilter = 'BigData*'
                            cmd += ' --test_bigdata'
                        if moduleTestFilter is not None and moduleTestFilter != '':
                            cmd += ' --gtest_filter=' + moduleTestFilter
                        cmd += (' --gtest_output=xml:%s' % resultsFileOnSlave) + ' -t ' + test + \
                                (' ' + ' '.join(performance_samples) if isPerf else ' -a')
                    else:
                        pythonDataOption = ''
                        if self.osType != OSType.WINDOWS:
                            pythonDataOption = '--data /opt/build/python_test_data'  # TODO Move to env vars on slave
                        else:
                            pythonDataOption = '--data c:\\utils\\python_test_data'  # TODO Move to env vars on slave
                        # runner is 'python2' or 'python3' same as test
                        cmd += ('%(runner)s ../%(path)s/modules/python/test/test.py --repo ../%(path)s %(data)s -v 2>&1' % \
                                {'path': self.SRC_OPENCV, 'data': pythonDataOption, 'runner': test})
                    defer.returnValue(cmd)
                return command

            args = dict(name=hname, workdir=builddir,
                    command=getCommand(test, testFilter, resultsFileOnSlave), env=env, descriptionDone=hname, description=hname,
                    warnOnWarnings=True, maxTime=self.getTestMaxTime(isPerf), timeout=self.getTestTimeout(),
                    doStepIf=doStepIf, hideStepIf=hideStepIfDefault, logfiles={})
            if not self.isPrecommit or self.isPerf:
                if bool(self.getProperty('test_xml', default=self.testXML)):
                    args['logfiles'].update(
                            { getResultFileNameRenderer(testPrefix, test, testSuffix) : resultsFileOnSlave }
                    )
            if isPythonTest(test):
                step = CommandTestPy(**args)
            elif test == 'java':
                if isBranch24(self):
                    args['logfiles'].update({"junit-report": "modules/java/test/.build/testResults/junit-noframes.html"})
                else:
                    args['logfiles'].update({
                        "junit-report": "modules/java/pure_test/.build/testResults/junit-noframes.html",
                        "junit": "java_test/testResults/junit-noframes.html",  # since Jan 2018
                    })
                    args['lazylogfiles'] = True
                step = CommandTestJava(**args)
            else:
                step = CommandTestCPP(**args)
            if step is not None:
                steps.append(step)

            if uploadDir is not None and not (isPythonTest(test) or test == 'java'):
                def getCompletionCallback(
                        test=test, testPrefix=testPrefix, testSuffix=testSuffix,
                        doStepIfModule=doStepIfModule, haltOnFailure=haltOnFailure, resultsFileOnSlave=resultsFileOnSlave):
                    @defer.inlineCallbacks
                    def testStepCompletionCallback(teststep, results):
                        def getDestination(test, _uploadDir):
                            @renderer
                            @defer.inlineCallbacks
                            def destination(props):
                                uploadDir = yield interpolateParameter(_uploadDir, props)
                                dst = uploadDir
                                dst += yield interpolateParameter(getResultFileNameRenderer(testPrefix, test, testSuffix), props)
                                defer.returnValue(dst)
                            return destination
                        uploadStep = FileUpload(
                            workdir=builddir,
                            slavesrc=resultsFileOnSlave, masterdest=getDestination(test, uploadDir), mode=0644,
                            haltOnFailure=haltOnFailure, doStepIf=doStepIfModule, hideStepIf=hideStepIfDefault)
                        self.addStep(uploadStep, teststep)
                    return testStepCompletionCallback
                step.addCompletionCallback(getCompletionCallback())

        defer.returnValue(steps)

    @defer.inlineCallbacks
    def determineTests(self):
        exe = "%s python %s" % (self.envCmd, self.getRunPy())
        exe = exe.strip()
        p = {
            "tests_performance": "--list_short",
            "tests_accuracy": "--list_short -a",
            "tests_performance_main": "--list_short_main",
            "tests_accuracy_main": "--list_short_main -a"
        }
        for prop, args in p.items():
            def extract(rc, stdout, stderr):
                if rc == 0:
                    return {prop: " ".join(sorted(str(stderr).split()))}
                else:
                    return {prop: ""}
            yield self.processStep(
                SetPropertyFromCommand(
                    command = "%s %s" % (exe, args),
                    extract_fn = extract,
                    workdir = "build",
                    env=self.env,
                    hideStepIf=hideStepIfSuccessSkipFn))

    def getTestList(self, isPerf = False):
        prop = "tests_performance" if isPerf else "tests_accuracy"
        main = self.getProperty(prop + "_main").split()
        if not self.isContrib:
            res = main
        else:
            all = self.getProperty(prop).split()
            res = [i for i in all if i not in main or i in ['java', 'python', 'python2', 'python3']]  # run bindings tests for contrib too
        if not self.runPython:
            res = [i for i in res if not isPythonTest(i)]
        modulesFilter = self.getProperty('modules_filter')
        if modulesFilter:
            modulesList = modulesFilter.split(',')
            return [i for i in res if i in modulesList]
        modules_force_list = str(self.getProperty('modules_force', '')).split(',')
        return [i for i in res if (i not in self.getTestBlacklist(isPerf)) or (i in modules_force_list)]

    @defer.inlineCallbacks
    def testAll(self):

        if self.osType == OSType.ANDROID and self.androidDevice is None:
            return

        steps = []

        @defer.inlineCallbacks
        def add_tests(is24, acc_list = None, perf_list = None):
            env_backup = self.env.copy()

            testSuffix = '-' + self.plainRunName if self.plainRunName else ''
            if acc_list:
                accuracyTests = yield self.addTestSteps(False, acc_list, testSuffix=testSuffix)
                steps.extend(accuracyTests)
            if perf_list:
                if is24:
                    perfTests = yield self.addTestSteps(True, perf_list, performance_samples=['--check'], implementation='plain', testSuffix=testSuffix)
                else:
                    perfTests = yield self.addTestSteps(True, perf_list, performance_samples=['--check'], testSuffix=testSuffix)
                steps.extend(perfTests)

            self.env = env_backup

        yield add_tests(True, self.getTestList(False), self.getTestList(True))

        parallel_N = self.getProperty('parallel_tests', 4)
        print('Running {} tests in parallel ({})'.format(len(steps), parallel_N))
        yield self.bb_build.processStepsInParallel(steps, parallel_N)


    @defer.inlineCallbacks
    def upload_release(self):
        path = getUploadPathTemplate()
        step = DirectoryUpload(
                name='upload artifacts',
                slavesrc='release',
                workdir='build',
                masterdest=Interpolate(getExportDirectory() + path),
                url=Interpolate(getExportURL() + path))
        yield self.processStep(step)


    def getFactoryProperties(self, props):
        if self.platform:
            props['platform'] = self.platform
        if not self.isPrecommit and self.branch:
            props['branch'] = self.branch
        return props


    #
    # Helpers
    #
    def name(self):
        return self.useName

    def nameprefix(self):
        if self.useNamePrefix is None:
            return ''
        return self.useNamePrefix

    def getNameSuffix(self):
        res = '' if self.buildShared else '-static'
        if self.buildImage and isinstance(self.buildImage, (list, tuple)) and self.buildImage[0]:
            res += self.buildImage[0]
        if self.cmake_toolset:
            res += self.cmake_toolset[0]
        if self.isDebug:
            res += '-debug'
        return res


    @defer.inlineCallbacks
    def after_build_steps(self):
        yield None

    @defer.inlineCallbacks
    def after_tests_steps(self):
        yield None

    @defer.inlineCallbacks
    def optional_build_gapi_standalone(self):
        ade_dir = self.getProperty('build_gapi_standalone', default=None)
        if ade_dir:
            ade_dir = str(ade_dir)
            if re.search(r'(/|\\)', ade_dir) is not None:
                print('ERROR: Not allowed build_gapi_standalone value: ' + ade_dir)
                ade_dir = None
        if ade_dir:
            step = RemoveDirectory(
                dir='build_ade', hideStepIf=lambda result, s: result == SUCCESS,
                haltOnFailure=True)
            yield self.processStep(step)
            step = RemoveDirectory(
                dir='build_gapi_standalone', hideStepIf=lambda result, s: result == SUCCESS,
                haltOnFailure=True)
            yield self.processStep(step)
            step = MakeDirectory(
                dir='build_ade', hideStepIf=lambda result, s: result == SUCCESS,
                haltOnFailure=True)
            yield self.processStep(step)
            step = MakeDirectory(
                dir='build_gapi_standalone', hideStepIf=lambda result, s: result == SUCCESS,
                haltOnFailure=True)
            yield self.processStep(step)

            yield self.cmake(builddir='build_ade', cmakedir='../build/3rdparty/ade/' + ade_dir, desc='cmake ade',
                cmakepars={
                    'CMAKE_BUILD_TYPE': 'Debug' if self.isDebug else 'Release',
                    'CMAKE_INSTALL_PREFIX': 'install',
                })
            yield self.compile(config='debug' if self.isDebug else 'release', builddir='build_ade', target='install', desc='build ade')

            yield self.cmake(builddir='build_gapi_standalone', cmakedir='../' + self.SRC_OPENCV + '/modules/gapi', desc='cmake gapi standalone',
                cmakepars={
                    'CMAKE_BUILD_TYPE': 'Debug' if self.isDebug else 'Release',
                    'ade_DIR': self.getProperty('workdir') + '/build_ade/install/share/ade',
                    'CMAKE_INSTALL_PREFIX': 'install',
                })
            if self.osType == OSType.WINDOWS:
                yield self.compile(config='debug' if self.isDebug else 'release', builddir='build_gapi_standalone', desc='build gapi standalone')
            else:
                yield self.compile(config='debug' if self.isDebug else 'release', builddir='build_gapi_standalone', target='all', desc='build gapi standalone')
        yield None
