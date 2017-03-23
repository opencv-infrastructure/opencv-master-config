from twisted.internet import defer

from build_utils import OSType, isBranch24, isNotBranch24
from constants import PLATFORM_DEFAULT
from factory_ipp import IPP_factory as BaseFactory

class OCL_factory(BaseFactory):

    def __init__(self, *args, **kwargs):
        self.useOpenCL = kwargs.pop('useOpenCL', None)
        self.buildOpenCL = kwargs.pop('buildOpenCL', self.useOpenCL)
        self.testOpenCL = kwargs.pop('testOpenCL', self.useOpenCL)
        self.testOpenCLWithPlain = kwargs.pop('testOpenCLWithPlain', False)
        BaseFactory.__init__(self, *args, **kwargs)
        if self.testOpenCL:
            self.plainRunName = 'plain' if not self.useIPP else 'ipp' if self.useIPP == True else 'ippicv'
            self.openCLDevicePrefix = '' if not self.useIPP else 'ipp-' if self.useIPP == True else 'ippicv-'
        if self.useName is None:
            self.useName = 'noOCL' if self.buildOpenCL == False else None

    def initConstants(self):
        BaseFactory.initConstants(self)
        self.cmakepars['WITH_OPENCL'] = 'ON' if self.buildOpenCL else 'OFF'
        self.cmakepars['WITH_CUDA'] = 'OFF'

    def _getOpenCLDeviceMap(self):
        assert not (self.platform is None or self.platform == '')
        if self.platform == PLATFORM_DEFAULT:
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
        if not self.testOpenCL and isBranch24(self):
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

            yield self.bb_build.processStepsInParallel(steps, self.getProperty('parallel_tests', 4) if isNotBranch24(self) else 1)

        if not self.testOpenCL or self.testOpenCLWithPlain:
            env_backup = self.env.copy()
            self.env['OPENCV_OPENCL_RUNTIME'] = ''
            self.env['OPENCV_OPENCL_DEVICE'] = 'disabled'  # for static OpenCL builds
            yield BaseFactory.testAll(self)
            self.env = env_backup
