import socket

from twisted.internet import defer

from buildbot.steps.shell import ShellCommand
from buildbot.plugins import util

from command_test import CommandTest
from command_test_cpp import GoogleUnitTestsObserver
from build_utils import OSType, isBranch24
from factory_ocl import OCL_factory as BaseFactory
from devices import devices as global_devices

armv7lock = util.MasterLock("armv7lock")
armv8lock = util.MasterLock("armv8lock")

# each device should provide "arch" property
DEVICE_ARCH_ARMv7 = "armv7"
DEVICE_ARCH_ARMv8 = "armv8"

# TODO: use it do detect actual devices
def getAvailableDevices(devices):
    result = []
    for d in devices:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((d['host'], d['port']))
            result.append(d)
        except IOError:
            s.close()
    return result



class ARMDeploy(ShellCommand):
    """ Make rsync call: 'sources' is list of strings and 'dest' is string """
    def __init__(self, sources, dest, **kwargs):
        # rsync -a bin lib ../self.SRC_OPENCV_EXT/testdata ubuntu@seco-gpu-devkit:.
        cmd = ["rsync", "-a", "--delete", "-v"]
        cmd.extend(sources)
        cmd.append(dest)
        ShellCommand.__init__(self, command=" ".join(cmd), **kwargs)



class ARMTest(CommandTest):
    """ Run distributed testing on remote device using gtest sharding feature """
    def __init__(self, **kwargs):
        self.devices = devices
        self.shardCount = sum([d['cores'] for d in self.devices])
        CommandTest.__init__(self, command=self.getBigCommand(), logfiles=self.getLogFiles(),
                             description="test %d shards" % self.shardCount,
                             descriptionDone="test %d shards" % self.shardCount,
                             warnOnWarnings=True,
                             **kwargs)
        for index in range(self.shardCount):
            self.addLogObserver(self.getLogName(index), GoogleUnitTestsObserver())

    def getBigCommand(self):
        pieces = []
        startIndex = 0
        for d in self.devices:
            pieces = pieces + [self.getSmallCommand(d, core + startIndex) for core in range(d['cores'])]
            startIndex = startIndex + d['cores']
        return " ; ".join(pieces) + " ; wait"

    def getSmallCommand(self, device, shardIndex):
        return '(ssh %s@%s "%s" > %s &)' % (device['user'], device['host'], self.getRemoteCommand(shardIndex), self.getLogName(shardIndex))

    def getRemoteCommand(self, shardIndex):
        smallPieces = ["cd work",
                       "export GTEST_SHARD_INDEX=%d" % shardIndex,
                       "export GTEST_TOTAL_SHARDS=%d" % self.shardCount,
                       "export LD_LIBRARY_PATH=lib",
                       "export OPENCV_TEST_DATA_PATH=testdata",
                       "./bin/opencv_test_core",
                       "./bin/opencv_test_imgproc",
                       "./bin/opencv_test_calib3d --gtest_filter=-*fisheyeTest.rectify*",
                       "./bin/opencv_test_features2d",
                       "./bin/opencv_test_photo",
                       "./bin/opencv_test_video",
                       "./bin/opencv_perf_core --perf_force_samples=1 --perf_min_samples=1",
                       "./bin/opencv_perf_imgproc --perf_force_samples=1 --perf_min_samples=1",
                       "./bin/opencv_perf_calib3d --perf_force_samples=1 --perf_min_samples=1 --gtest_filter=-*fisheyeTest.rectify*",
                       "./bin/opencv_perf_features2d --perf_force_samples=1 --perf_min_samples=1",
                       "./bin/opencv_perf_photo --perf_force_samples=1 --perf_min_samples=1",
                       "./bin/opencv_perf_video --perf_force_samples=1 --perf_min_samples=1"]
        return " ; ".join(smallPieces)

    def getLogFiles(self):
        return {self.getLogName(shardIndex): self.getLogName(shardIndex) for shardIndex in range(self.shardCount)}

    def getLogName(self, shardIndex):
        return "log_{0}.txt".format(shardIndex + 1)



class TemperatureCommand(ShellCommand):
    '''
    Acquire temperature using passed shell command
        'command' -- passed to ShellCommand, should return single floating-point number
        'divisor' -- used to convert evaluated temperature to Celsius degrees
        'host' -- used in description text
    other parameters are passed to ShellCommand
    '''
    def __init__(self, divisor=1, **kwargs):
        ShellCommand.__init__(self, logEnviron = False, **kwargs)
        self.divisor = divisor
    def describe(self, done=False):
        if done:
            try:
                t = self.getLog("stdio").getText()
                return ["{temp:4.1f} C".format(temp=float(t) / self.divisor)]
            except:
                return ["n/a"]
        else:
            return ["acquire", "temperature"]



class ARMTemperatureCPU(TemperatureCommand):
    cmd = 'ssh {user}@{host} "cat /sys/class/thermal/thermal_zone0/temp"'
    def __init__(self, device, **kwargs):
        TemperatureCommand.__init__(self,
                                    command=ARMTemperatureCPU.cmd.format(**device),
                                    divisor=1000,
                                    **kwargs)



class ARMTemperatureHDD(TemperatureCommand):
    cmd = """ssh {user}@{host} "netcat localhost 7634 | cut -d '|' -f 4" """
    def __init__(self, device, **kwargs):
        TemperatureCommand.__init__(self,
                                    command=ARMTemperatureHDD.cmd.format(**device),
                                    divisor=1,
                                    **kwargs)


class ARMFactory(BaseFactory):
    def __init__(self, *args, **kwargs):
        self.device_arch = kwargs.pop("device_arch", None)
        myargs = dict(
            osType=OSType.LINUX,
            is64=None,
            buildExamples=False,
        )
        myargs.update(kwargs)
        BaseFactory.__init__(self, *args, **myargs)

    @defer.inlineCallbacks
    def testAll(self):
        steps = []
        devices = [d for d in global_devices if d.arch == self.device_arch]

        # deploy
        for d in devices:
            steps.append(
                ARMDeploy(name="deploy to {host}".format(**d),
                          sources=["bin", "lib", "../%s/testdata" % self.SRC_OPENCV_EXT, "../%s/modules/python/test/*.py" % self.SRC_OPENCV],
                          dest="{user}@{host}:work".format(**d),
                          workdir='build')
           )

        # check temperature
        for d in devices:
            steps.append(ARMTemperatureCPU(name="cpu before run [{host}]".format(**d), device=d))

        if len(devices) > 0:
            # run tests, use 'devices' list
            steps.append(ARMTest(name="distributed test"))
            # run python test on one device
            steps.append(
                ShellCommand(name="python test",
                             warnOnWarnings=True,
                             command='ssh {user}@{host} "'\
                                     'cd work ; '\
                                     'export OPENCV_TEST_DATA_PATH=testdata ; '\
                                     'export LD_LIBRARY_PATH=lib ; '\
                                     'export PYTHONPATH=lib ; '\
                                     'python test.py -v 2>&1'\
                                     '"'.format(**devices[0])))

        # check temperature
        for d in devices:
            steps.append(ARMTemperatureCPU(name="cpu after run [{host}]".format(**d), device=d))

        yield self.bb_build.processStepsInParallel(steps, 1)  # No parallel launch


class ARMv7Factory(ARMFactory):
    def __init__(self, *args, **kwargs):
        myargs = dict(
            useName='ARMv7',
            device_arch=DEVICE_ARCH_ARMv7,
            locks = [armv7lock.access("exclusive")],
        )
        myargs.update(kwargs)
        ARMFactory.__init__(self, *args, **myargs)

    def set_cmake_parameters(self):
        BaseFactory.set_cmake_parameters(self)
        self.cmakepars['CMAKE_TOOLCHAIN_FILE'] = '../%s/platforms/linux/arm-gnueabi.toolchain.cmake' % self.SRC_OPENCV
        self.cmakepars['GCC_COMPILER_VERSION'] = '4.8'
        self.cmakepars['ENABLE_NEON'] = 'YES'
        self.cmakepars['ENABLE_VFPV3'] = 'YES'
        is24 = isBranch24(self)
        self.cmakepars['PYTHON_INCLUDE_PATH' if is24 else 'PYTHON2_INCLUDE_PATH'] = \
            '/usr/arm-linux-gnueabihf/include/python2.7'
        self.cmakepars['PYTHON_LIBRARIES' if is24 else 'PYTHON2_LIBRARIES'] = \
            '/usr/arm-linux-gnueabihf/lib/libpython2.7.so'
        self.cmakepars['PYTHON_NUMPY_INCLUDE_DIR' if is24 else 'PYTHON2_NUMPY_INCLUDE_DIRS'] = \
            '/usr/arm-linux-gnueabihf/include/python2.7'


class ARMv8Factory(ARMFactory):
    def __init__(self, *args, **kwargs):
        myargs = dict(
            useName='ARMv8',
            device_arch=DEVICE_ARCH_ARMv8,
            locks = [armv8lock.access("exclusive")],
        )
        myargs.update(kwargs)
        ARMFactory.__init__(self, *args, **myargs)

    def set_cmake_parameters(self):
        BaseFactory.set_cmake_parameters(self)
        self.cmakepars['CMAKE_TOOLCHAIN_FILE'] = '../%s/platforms/linux/aarch64-gnu.toolchain.cmake' % self.SRC_OPENCV
        self.cmakepars['GCC_COMPILER_VERSION'] = '4.8'
