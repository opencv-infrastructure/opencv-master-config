from twisted.internet import defer

from buildbot.steps.source.git import Git
from buildbot.steps.shell import ShellCommand
from buildbot.steps.slave import MakeDirectory

from factory_common import CommonFactory
from build_utils import *



class AndroidPackFactory(CommonFactory):
    ''' For complete Android pack builds '''
    def __init__(self, *args, **kwargs):
        myargs = dict(
            osType=OSType.ANDROID, is64=True
        )
        myargs.update(kwargs)
        CommonFactory.__init__(self, *args, **myargs)


    @defer.inlineCallbacks
    def run_build_script(self):
        extra_opts = ['--extra_pack', '2.4.13:/opt/android/pack_2.4/'] if isBranch34(self) else []
        if self.buildWithContrib:
            extra_opts += ['--extra_modules_path', '../' + self.SRC_OPENCV_CONTRIB + '/modules']
        config_prop = self.getProperty('android_pack_config', default=None)
        if config_prop:
            extra_opts += ['--config', str(config_prop)]
        env = self.env.copy()
        if isBranch24(self):
            env['ANDROID_NDK'] = '/opt/android/android-ndk-r8e'
        cmd = [
            'python',
            '../' + self.SRC_OPENCV + '/platforms/android/build_sdk.py',
            '--build_doc',
        ] + extra_opts + [
            '.',
            '../' + self.SRC_OPENCV
        ]
        step = \
            ShellCommand(
                name="build sdk",
                command=self.envCmdList + cmd,
                workdir='build',
                env=env)
        yield self.processStep(step)


    @defer.inlineCallbacks
    def run_test_scripts(self):
        if isBranch24(self):
            return
        step = \
            ShellCommand(
                name="test cmake",
                command=self.envCmd + ' python ../' + self.SRC_OPENCV + '/platforms/android/build-tests/test_cmake_build.py OpenCV-android-sdk/sdk/native/jni',
                workdir='build',
                env=self.env)
        yield self.processStep(step)
        if isBranch34(self):  # OpenCV <= 3.4.5
            step = \
                ShellCommand(
                    name="test ant",
                    command=self.envCmd + ' python ../' + self.SRC_OPENCV + '/platforms/android/build-tests/test_ant_build.py OpenCV-android-sdk/sdk/java OpenCV-android-sdk/samples',
                    workdir='build',
                    env=self.env)
            yield self.processStep(step)
            step = \
                ShellCommand(
                    name="test ndk",
                    command=self.envCmd + ' python ../' + self.SRC_OPENCV + '/platforms/android/build-tests/test_ndk_build.py OpenCV-android-sdk/sdk/native/jni',
                    workdir='build',
                    env=self.env)
            yield self.processStep(step)
        if self.getProperty('test_gradle', default=None):
            step = \
                ShellCommand(
                    name="test gradle",
                    command=self.envCmd + ' ../' + self.SRC_OPENCV + '/platforms/android/build-tests/test_gradle.sh OpenCV-android-sdk',
                    workdir='build',
                    env=self.env)
            yield self.processStep(step)


    @defer.inlineCallbacks
    def pack_results(self):
        step = MakeDirectory(dir = "build/release")
        yield self.processStep(step)
        step = ShellCommand(
                name = "pack results",
                workdir = "build",
                command = ["zip", "-r", "-9", "-y", "release/OpenCV4Android.zip", "OpenCV-android-sdk"])
        yield self.processStep(step)


    @defer.inlineCallbacks
    def build(self):
        yield self.run_build_script()
        yield self.run_test_scripts()
        yield self.pack_results()
        yield self.upload_release()

    @defer.inlineCallbacks
    def determineTests(self):
        yield None

    @defer.inlineCallbacks
    def testAll(self):
        yield None
