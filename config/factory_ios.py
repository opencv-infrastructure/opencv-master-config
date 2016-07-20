import re

from twisted.internet import defer

from buildbot.steps.shell import ShellCommand, Compile
from buildbot.steps.slave import MakeDirectory

from build_utils import OSType, isBranch24
from factory_ocl import OCL_factory as BaseFactory


class iOSFactory(BaseFactory):

    def __init__(self, *args, **kwargs):
        myargs = dict(
            useName='iOS',
            osType=OSType.MACOSX, is64=None, buildExamples=False,
        )
        myargs.update(kwargs)
        BaseFactory.__init__(self, *args, **myargs)


    @defer.inlineCallbacks
    def buildFramework(self):
        step = \
            Compile(name="build framework",
                warningPattern=re.compile(r'.*(?<!libtool: )warning[: ].*', re.I | re.S),
                warnOnWarnings=True,
                workdir='build',
                command="python ../%s/platforms/ios/build_framework.py build_ios" % self.SRC_OPENCV)
        yield self.processStep(step)

    @defer.inlineCallbacks
    def buildContribFramework(self):
        step = \
            Compile(name="build contrib framework",
                    warningPattern=re.compile(r'.*(?<!libtool: )warning[: ].*', re.I | re.S),
                    warnOnWarnings=True,
                    workdir='build',
                    command="python ../%s/platforms/ios/build_framework.py --contrib ../%s build_ios_contrib" % (self.SRC_OPENCV, self.SRC_OPENCV_CONTRIB))
        yield self.processStep(step)


    @defer.inlineCallbacks
    def build(self):
        if not self.isContrib:
            yield self.buildFramework()
        if self.buildWithContrib:
            yield self.buildContribFramework()

        if self.isPrecommit:
            return

        step = MakeDirectory(dir="build/release")
        yield self.processStep(step)
        if not self.isContrib:
            step = \
                ShellCommand(
                    name = "pack opencv",
                    workdir = "build/build_ios",
                    command=["zip", "-r", "-9", "-y", "../release/opencv2.framework.zip", "opencv2.framework"])
            yield self.processStep(step)
        if self.buildWithContrib:
            step = \
                ShellCommand(
                    name="pack opencv_contrib",
                    workdir="build/build_ios_contrib",
                    command=["zip", "-r", "-9", "-y", "../release/opencv2_contrib.framework.zip", "opencv2.framework"])
            yield self.processStep(step)

        yield self.upload_release()

    @defer.inlineCallbacks
    def determineTests(self):
        yield None

    @defer.inlineCallbacks
    def testAll(self):
        yield None
