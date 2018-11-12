from twisted.internet import defer

from build_utils import OSType, isBranch24, isNotBranch24
from constants import PLATFORM_ANY, PLATFORM_DEFAULT, PLATFORM_SKYLAKE, PLATFORM_SKYLAKE_X
from factory_ipp import IPP_factory as BaseFactory

class OCL_factory(BaseFactory):

    def __init__(self, *args, **kwargs):
        self.useOpenCL = kwargs.pop('useOpenCL', None)
        self.buildOpenCL = kwargs.pop('buildOpenCL', self.useOpenCL)
        self.testOpenCL = kwargs.pop('testOpenCL', self.useOpenCL)
        self.testOpenCLWithPlain = kwargs.pop('testOpenCLWithPlain', False)
        BaseFactory.__init__(self, *args, **kwargs)
        self.openCLDevicePrefix = ''
        if self.testOpenCL:
            self.plainRunName = 'plain' if not self.useIPP else 'ipp' if self.useIPP == True else 'ippicv'
            self.openCLDevicePrefix = '' if not self.useIPP else 'ipp-' if self.useIPP == True else 'ippicv-'
        if self.useName is None:
            self.useName = 'noOCL' if self.buildOpenCL == False else None
        if self.platform == PLATFORM_ANY and self.testOpenCL and 'linux-3' in self.useSlave and \
            (not self.builder_properties or not 'buildworker' in self.builder_properties):
            print('OCL: Excluding linux-3 from builder: {} (props = {})'.format(self.getName(), str(self.builder_properties)))
            self.useSlave.remove('linux-3')

    @defer.inlineCallbacks
    def runPrepare(self):
        if self.getProperty('test_opencl', default=None):
            test_opencl = True if self.getProperty('test_opencl', default=None) in ['ON', '1', 'TRUE', 'True'] else False
            self.buildOpenCL = test_opencl
            self.testOpenCL = test_opencl

        if isBranch24(self):
            self.testOpenCL = False

        if self.testOpenCL and self.dockerImage is None:
            if self.osType == OSType.LINUX:
                self.dockerImage = (None, 'ubuntu:16.04') if not (self.is64 is False) else (None, 'ubuntu32:16.04')

        yield BaseFactory.runPrepare(self)


    def set_cmake_parameters(self):
        BaseFactory.set_cmake_parameters(self)
        self.cmakepars['WITH_OPENCL'] = 'ON' if self.buildOpenCL else 'OFF'
        self.cmakepars['WITH_CUDA'] = 'OFF'


    def _getOpenCLDeviceMap(self):
        assert not (self.platform is None or self.platform == '')
        if self.platform in [PLATFORM_ANY, PLATFORM_DEFAULT, PLATFORM_SKYLAKE, PLATFORM_SKYLAKE_X]:
            return {'opencl' : ':GPU:'}
        assert False

    def getOpenCLDeviceMap(self):
        if self.testOpenCL == False:
            return {}
        deviceMap = self._getOpenCLDeviceMap()
        deviceMapNew = {}
        for devID in sorted(deviceMap.keys()):
            deviceMapNew[self.openCLDevicePrefix + devID] = deviceMap[devID]
        return deviceMapNew

    @defer.inlineCallbacks
    def determineTests(self):
        if self.testOpenCL and isBranch24(self):
            self.setProperty("tests_performance", "ocl", "determineTests")
            self.setProperty("tests_performance_main", "ocl", "determineTests")
            self.setProperty("tests_accuracy", "ocl", "determineTests")
            self.setProperty("tests_accuracy_main", "ocl", "determineTests")
        else:
            yield BaseFactory.determineTests(self)

    def getTestBlacklist(self, isPerf=False):
        res = BaseFactory.getTestBlacklist(self, isPerf)
        if not self.testOpenCL or isBranch24(self):
            res.append("ocl")
        return res

    @defer.inlineCallbacks
    def testAll(self):
        if self.testOpenCL:
            steps = []

            env_backup = self.env.copy()

            if not self.isPrecommit:
                self.env['OPENCV_TEST_OCL_LOOP_TIMES'] = '10'

            deviceMap = self.getOpenCLDeviceMap()
            for devID in deviceMap.keys():
                self.env['OPENCV_OPENCL_DEVICE'] = deviceMap[devID]
                testSuffix = '-%s' % devID
                accuracyTests = yield self.addTestSteps(False, self.getTestList(False), testSuffix=testSuffix)
                perfTests = yield self.addTestSteps(True, self.getTestList(True), performance_samples=['--check'], testSuffix=testSuffix)
                steps.extend(accuracyTests)
                steps.extend(perfTests)

            self.env['OPENCV_OPENCL_DEVICE'] = 'DISABLED'
            del self.env['OPENCV_OPENCL_DEVICE']  # TODO Workaround for ocl module based tests (ocl in bioinspired/nonfree)

            self.env = env_backup

            yield self.bb_build.processStepsInParallel(steps, min(int(self.getProperty('parallel_tests', 2)), 2) if isNotBranch24(self) else 1)

        if not self.testOpenCL or self.testOpenCLWithPlain:
            env_backup = self.env.copy()
            self.env['OPENCV_OPENCL_RUNTIME'] = ''
            self.env['OPENCV_OPENCL_DEVICE'] = 'disabled'  # for static OpenCL builds
            yield BaseFactory.testAll(self)
            self.env = env_backup
