import datetime
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
from constants import PLATFORM_DEFAULT, PLATFORM_INTEL

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

    def __init__(self, **kwargs):
        self.forceSched = kwargs.pop('forceSched', {})

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
        self.compiler = kwargs.pop('compiler', None)
        self.is64 = kwargs.pop('is64', True if self.osType in [OSType.WINDOWS, OSType.LINUX] else None)
        self.buildShared = kwargs.pop('buildShared', True)
        assert not (self.buildShared is None)
        self.buildDocs = kwargs.pop('buildDocs', False)
        assert not (self.buildDocs is None)
        self.buildExamples = kwargs.pop('buildExamples', True)
        assert not (self.buildExamples is None)
        self.useSSE = kwargs.pop('useSSE', None)
        self.useAVX = kwargs.pop('useAVX', None)
        self.isDebug = kwargs.pop('isDebug', False)
        self.runPython = kwargs.pop('runPython', self.osType != OSType.ANDROID and not (self.isDebug and self.osType == OSType.WINDOWS))
        self.isPrecommit = kwargs.pop('isPrecommit', False)
        self.isPerf = kwargs.pop('isPerf', False)
        self.buildWithContrib = kwargs.pop('buildWithContrib', self.branch != '2.4') # Build with opencv_contrib
        self.isContrib = kwargs.pop('isContrib', False)
        self.envCmd = kwargs.pop('envCmd', 'buildenv')
        self.env = kwargs.pop('env', {}).copy()
        assert type(self.env) is dict
        self.cmake_generator = kwargs.pop('cmake_generator', None)
        self.cmakepars = kwargs.pop('cmake_parameters', {})
        self.r_warning_pattern = re.compile(r'.*warning[: ].*', re.I | re.S)

        BuilderNewStyle.__init__(self, **kwargs)

        if self.useSlave is None:
            if self.platform == PLATFORM_DEFAULT:
                if self.osType == OSType.LINUX:
                    if self.is64 is None or self.is64:
                        self.useSlave = ['linux-slave-x64']
                        if self.isPrecommit:
                            self.useSlave = ['linux-slave-x64-2', 'linux-slave-x64']
                elif self.osType == OSType.WINDOWS:
                    self.useSlave = ['windows-slave-x64-1', 'windows-slave-x64-2']
                elif self.osType == OSType.MACOSX or self.osType == OSType.ANDROID:
                    self.useSlave = ['macosx-slave']
                    if self.isPrecommit:
                        self.useSlave = ['macosx-slave-2', 'macosx-slave']
            elif self.platform == PLATFORM_INTEL:
                if self.osType == OSType.WINDOWS:
                    self.useSlave = ['windows-slave-x64-intel']

        if self.isPrecommit:
            self.env['BUILD_PRECOMMIT'] = '1'


    def onNewBuild(self):
        BuilderNewStyle.onNewBuild(self)
        self.env = self.env.copy()
        self.cmakepars = self.cmakepars.copy()
        if self.isPrecommit:
            prefix = self.bb_requests[0].properties.getProperty('branch', default=None)
            if prefix and prefix != 'master':
                self.SRC_OPENCV = prefix + '/' + self.SRC_OPENCV
                self.SRC_OPENCV_EXT = prefix + '/' + self.SRC_OPENCV_EXT
                self.SRC_OPENCV_CONTRIB = prefix + '/' + self.SRC_OPENCV_CONTRIB

    def getTags(self):
        res = list(BuilderNewStyle.getTags(self))

        # takes one of 'master', 'master-contrib', '2.4'
        second = 'master'
        if self.isContrib:
            second = 'master-contrib'
        elif self.branch == '2.4':
            second='2.4'

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
                run_py.append(' --configuration="Debug"')
            if self.androidABI:
                run_py.append(' --android_propagate_opencv_env --android_test_data_path /data/local/tmp/opencv/testdata/')
                if self.androidDevice:
                    run_py.append(' --serial %s' % self.androidDevice)
            return run_py

    def getTestBlacklist(self):
        '''
        list of tests to skip, due to some problems:
        - java: should be fixed
        - tracking: too long (> 24 hrs), should be optimized
        - dnn: should be fixed
        - viz: needs OpenGL windows
        - shape: should be fixed
        - gpu: not tested yet
        '''
        if isBranch24(self):
            return ["gpu", "java"]
        else:
            return ["java", "tracking", "dnn", "viz", "shape", "rgbd", "stereo"]

    def getTestMaxTime(self, isPerf):
        ''' total timeout for test execution, seconds '''
        if self.isPrecommit:
            return 40 * 60
        elif isPerf:
            return 120 * 60
        else:
            return 60 * 60

    def getTestTimeout(self):
        ''' timeout for test execution without output, seconds '''
        if self.isPrecommit and self.isDebug != True:
            return 3 * 60
        else:
            return 10 * 60

    @defer.inlineCallbacks
    def run(self):
        self.buildWithContrib = self.buildWithContrib and isNotBranch24(self)
        yield self.initialize()
        yield self.cleanup_builddir()
        yield self.checkout_sources()
        yield self.build()
        yield self.determineTests()
        yield self.testAll()
        if self.bb_build.result == SUCCESS and self.isPrecommit != True:
            yield self.cleanup_builddir()


    @defer.inlineCallbacks
    def runCleanup(self):
        # TODO Forced cleanup: yield self.cleanup_builddir()
        yield None


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
        if self.platform and self.platform != PLATFORM_DEFAULT:
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
        assert not self.envCmd is None
        self.envCmd += ' '

        if self.osType != OSType.ANDROID:
            if self.compiler is None:
                if self.osType == OSType.WINDOWS:
                    self.compiler = WinCompiler.VC12

            if (not 'BUILD_ARCH' in self.env) and (self.is64 is not None):
                if self.is64:
                    self.env['BUILD_ARCH'] = 'x64'
                else:
                    self.env['BUILD_ARCH'] = 'x86'
            if (not 'BUILD_COMPILER' in self.env) and (self.compiler is not None):
                self.env['BUILD_COMPILER'] = self.compiler

            if self.cmake_generator is None:
                self.cmake_generator = WinCompiler.getCMakeGenerator(self.compiler, self.is64)

    @defer.inlineCallbacks
    def initialize(self):
        timestamp = datetime.datetime.now()
        timestamp_str = timestamp.strftime('%Y%m%d-%H%M%S')
        prop_name = 'timestamp' if not self.hasProperty('timestamp') else 'my_timestamp'
        self.setProperty(prop_name, timestamp_str, 'Initialize Step')

        # run buildenv with dummy command to remove Git index.lock
        env = self.env.copy()
        env['BUILD_INITIALIZE'] = '1'
        step = ShellCommand(name='init', descriptionDone=' ', description=' ',
                command=self.envCmd + 'echo Initialize', env=env, workdir='.',
                haltOnFailure=True)
        yield self.processStep(step)


    @defer.inlineCallbacks
    def checkout_sources(self):
        getDescriptionOptions = {
             'always': True
        }
        step = Git(name='Fetch opencv', repourl=Interpolate('%(src:opencv:repository)s'), workdir=self.SRC_OPENCV,
            haltOnFailure=True, codebase='opencv', getDescription=getDescriptionOptions, mode='full', method='clean')
        yield self.processStep(step)
        step = Git(name='Fetch extra', repourl=Interpolate('%(src:opencv_extra:repository)s'), workdir=self.SRC_OPENCV_EXT,
            haltOnFailure=True, codebase='opencv_extra', getDescription=getDescriptionOptions, mode='full', method='clean')
        yield self.processStep(step)
        if self.buildWithContrib:
            step = Git(name='Fetch opencv_contrib', repourl=Interpolate('%(src:opencv_contrib:repository)s'), workdir=self.SRC_OPENCV_CONTRIB,
                haltOnFailure=True, codebase='opencv_contrib', getDescription=getDescriptionOptions, mode='full', method='clean')
            yield self.processStep(step)

        if self.isPrecommit:
            step = getMergeCommand('opencv', self.SRC_OPENCV)
            yield self.processStep(step)
            step = getMergeCommand('opencv_extra', self.SRC_OPENCV_EXT)
            yield self.processStep(step)
            if self.buildWithContrib:
                step = getMergeCommand('opencv_contrib', self.SRC_OPENCV_CONTRIB)
                yield self.processStep(step)


    @defer.inlineCallbacks
    def cleanup_builddir(self):
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

    def set_cmake_parameters(self):
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
            self.cmakepars['ENABLE_SSE2'] = 'ON'
            self.cmakepars['ENABLE_SSE3'] = 'ON'
            if not isBranch24(self):
                self.cmakepars['ENABLE_SSSE3'] = 'ON'
                self.cmakepars['ENABLE_SSE41'] = 'ON'
                self.cmakepars['ENABLE_SSE42'] = 'ON'
        elif self.useSSE == False:
            self.cmakepars['ENABLE_SSE2'] = 'OFF'
            self.cmakepars['ENABLE_SSE3'] = 'OFF'
            if not isBranch24(self) and not self.isDebug:
                self.cmakepars['ENABLE_SSSE3'] = 'OFF'
                self.cmakepars['ENABLE_SSE41'] = 'OFF'
                self.cmakepars['ENABLE_SSE42'] = 'OFF'
            if self.osType in [OSType.LINUX, OSType.ANDROID, OSType.MACOSX] and self.compiler == 'gcc':
                self.cmakepars['CMAKE_C_FLAGS'] = '-mno-sse2'
                self.cmakepars['CMAKE_CXX_FLAGS'] = '-mno-sse2'

        if self.useAVX:
            self.cmakepars['ENABLE_AVX'] = 'ON'
            self.cmakepars['ENABLE_AVX2'] = 'ON'

        if self.osType == OSType.ANDROID:
            del self.cmakepars['BUILD_SHARED_LIBS']
            self.cmakepars['CMAKE_TOOLCHAIN_FILE'] = '../%s/platforms/android/android.toolchain.cmake' % self.SRC_OPENCV
            if self.androidABI:
                self.cmakepars['ANDROID_ABI'] = self.androidABI
            if self.androidABI is None or self.androidABI.startswith('arm'):
                self.cmakepars['ANDROID_TOOLCHAIN_NAME'] = 'arm-linux-androideabi-4.8' if not self.is64 else 'aarch64-linux-android-4.9'

        if self.isDebug:
            self.cmakepars['CMAKE_BUILD_TYPE'] = 'Debug'

        if self.osType == OSType.LINUX and not isBranch24(self):
            self.cmakepars['WITH_OPENNI2'] = 'ON'
            self.cmakepars['WITH_GDAL'] = 'ON'
            self.cmakepars['PYTHON_DEFAULT_EXECUTABLE'] = '/usr/bin/python3.4'

        if self.buildWithContrib:
            self.cmakepars['OPENCV_EXTRA_MODULES_PATH'] = self.getProperty('workdir') + '/' + self.SRC_OPENCV_CONTRIB + '/modules'


    @defer.inlineCallbacks
    def cmake(self, builddir='build', cmakedir=None):
        if cmakedir is None:
            cmakedir = '../' + self.SRC_OPENCV
        self.set_cmake_parameters()
        @renderer
        @defer.inlineCallbacks
        def cmake_command(props):
            cmakepars = {}
            for key, value in self.cmakepars.items():
                value = yield interpolateParameter(value, props)
                cmakepars[key] = value
            cmakepars = ' '.join(['-D%s=%s' % (key, value) \
                for key, value in cmakepars.items() if len(value) > 0])

            command = self.envCmd + 'cmake'
            if self.cmake_generator:
                command += ' -G%s' % self.cmake_generator
            command += ' %s %s' % (cmakepars, cmakedir)
            defer.returnValue(command)

        step = Compile(command=cmake_command, env=self.env,
            workdir=builddir, name='cmake', haltOnFailure=True,
            descriptionDone='cmake', description='cmake',
            logfiles=dict(cache='CMakeCache.txt', vars='CMakeVars.txt'),
            warningPattern=self.r_warning_pattern, warnOnWarnings=True)
        yield self.processStep(step)


    @defer.inlineCallbacks
    def compile(self, builddir='build', config='release', target=None, useClean=False, desc=None, doStepIf=True, warningPattern=None, suppressionFile=None):
        @renderer
        def compileCommand(props):
            command = '%s cmake --build . --config %s' % (self.envCmd, config)
            if not target is None:
                command += ' --target %s' % target
            if useClean:
                command += ' --clean-first'
            cpus = props.getProperty('CPUs')
            if not cpus:
                cpus = 1
            elif cpus > 4:
                cpus = 4
            if self.compiler and self.compiler.startswith('vc'):
                command += ' -- /maxcpucount:%s /consoleloggerparameters:NoSummary' % cpus
            else:
                command += ' -- -j%s' % cpus
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
                    suppressionFile=suppressionFile)
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

        testPrefix = 'perf' if isPerf else 'test';
        for test in listOfTests:
            env = common_env.copy()
            step = None
            hname = '%s_%s%s%s' % (testPrefix, test, testSuffix, buildDesc)

            resultsFileOnSlave = 'results_%s_%s%s.xml' % (testPrefix, test, testSuffix)

            if self.androidABI:
                if isPythonTest(test) or test == 'java':
                    continue

            if isPythonTest(test):
                lib_sub_dir = '/lib'
                if test == 'python3':
                    lib_sub_dir += '/python3'
                if self.osType == OSType.WINDOWS:
                    lib_sub_dir += '/Release'
                env['PYTHONPATH'] = Interpolate('%(prop:workdir)s/' + builddir + lib_sub_dir)

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

            def getDoStepIf(test, doStepIf=doStepIf):
                doStepIf= doStepIf
                if isinstance(doStepIf, bool):
                    doStepIf = lambda _: doStepIf
                def fn(step):
                    if not doStepIf(step):
                        return False
                    modulesFilter = step.getProperty('modules_filter')
                    if modulesFilter:
                        modulesList = modulesFilter.split(',')
                        if test in modulesList:
                            return True
                        else:
                            return False
                    return True
                return fn
            doStepIfModule = getDoStepIf(test)

            args = dict(name=hname, workdir=builddir,
                    command=getCommand(test, testFilter, resultsFileOnSlave), env=env, descriptionDone=hname, description=hname,
                    warnOnWarnings=True, maxTime=self.getTestMaxTime(isPerf), timeout=self.getTestTimeout(),
                    doStepIf=doStepIfModule, hideStepIf=hideStepIfDefault, logfiles={})
            if not self.isPrecommit or self.isPerf:
                args['logfiles'] = { getResultFileNameRenderer(testPrefix, test, testSuffix) : resultsFileOnSlave }
            if isPythonTest(test):
                step = CommandTestPy(**args)
            elif test == 'java':
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
            res = [i for i in all if i not in main]
        if not isPerf and self.runPython and not self.isContrib:
            res.append('python')
            if isNotBranch24(self):
                if self.osType == OSType.LINUX or self.getProperty('slavename', '') == 'windows-slave-x64-intel':
                    res.append('python3')
        return [i for i in res if i not in self.getTestBlacklist()]

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

        yield self.bb_build.processStepsInParallel(steps, self.getProperty('parallel_tests', 4))


    @defer.inlineCallbacks
    def upload_release(self):
        path = getUploadPathTemplate()
        step = DirectoryUpload(
                name='upload artifacts',
                slavesrc='release',
                workdir='build',
                masterdest=Interpolate(getDirectoryForExport() + path),
                url=Interpolate(getDirectoryForExport(True) + path))
        yield self.processStep(step)


    def getFactoryProperties(self):
        props = {}
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
        if self.isDebug:
            res += '-debug'
        return res
