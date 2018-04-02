from twisted.internet import defer
from buildbot.steps.shell import ShellCommand
from buildbot.steps.transfer import FileUpload, DirectoryUpload
from buildbot.process.properties import Interpolate, renderer

from factory_ocl import OCL_factory as ParentClass
from build_utils import *

import re

class GenHTML(ShellCommand):
    def describe(self, done=False):
        res = ShellCommand.describe(self, done)
        if not done:
            return res
        # lines......: 8.6% (25196 of 294604 lines)
        # functions..: 13.6% (9093 of 66819 functions)
        lines_rx = re.compile(r'^\s*lines\.*: ([\d\.]+%)')
        functions_rx = re.compile(r'^\s*functions\.*: ([\d\.]+%)')
        for line in self.getLog('stdio').readlines():
            m = lines_rx.search(line)
            if m:
                res.append('lines: %s ; ' % m.group(1))
            m = functions_rx.search(line)
            if m:
                res.append('functions: %s ; ' % m.group(1))
        return res

class CoverageFactory(ParentClass):
    def __init__(self, **kwargs):
        useSlave = ['linux-1']
        branch = kwargs.get('branch', 'master')
        kwargs['useSlave'] = kwargs.pop('useSlave', useSlave)
        kwargs['dockerImage'] = kwargs.pop('dockerImage', (None, 'coverage' if branch != '2.4' else 'coverage:14.04'))
        ParentClass.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def runPrepare(self):
        yield ParentClass.runPrepare(self)
        self.setProperty('parallel_tests', 1)
        self.setProperty('CPUs', 2)  # high memory usage

    def set_cmake_parameters(self):
        ParentClass.set_cmake_parameters(self)
        self.cmakepars['ENABLE_COVERAGE'] = 'ON'
        self.cmakepars['ENABLE_PRECOMPILED_HEADERS'] = 'OFF'
        self.cmakepars['CPU_BASELINE'] = 'HOST'
        self.cmakepars['CPU_DISPATCH'] = ''

    @defer.inlineCallbacks
    def testAll(self):
        builddir = Interpolate('%(prop:builddir)s/build')
        step =ShellCommand(
            name='clean coverage',
            command='rm -rf coverage_html tmp*.gcno',
            workdir='build',
            env=self.env,
            haltOnFailure=False)
        yield self.processStep(step)

        step =ShellCommand(
            name='zero coverage',
            command=self.envCmd.split() + ['lcov', '--directory', builddir, '--zerocounters'],
            workdir='build',
            env=self.env,
            haltOnFailure=False)
        yield self.processStep(step)

        step =ShellCommand(
            name='init coverage',
            command=self.envCmd.split() + ['lcov', '--directory', builddir, '--capture', '--initial', '-o', 'opencv_base.info'],
            workdir='build',
            env=self.env,
            haltOnFailure=False)
        yield self.processStep(step)

        yield ParentClass.testAll(self)

        step = ShellCommand(
            name='run coverage',
            command=self.envCmd.split() + ['lcov', '--directory', builddir, '--capture', '-o', 'opencv_test.info'],
            workdir='build',
            env=self.env,
            haltOnFailure=False)
        yield self.processStep(step)

        step = ShellCommand(
            name='combine coverage',
            command=self.envCmd.split() + ['lcov',
                '-a', 'opencv_base.info',
                '-a', 'opencv_test.info',
                '-o', 'opencv_total.info'],
            workdir='build',
            env=self.env,
            haltOnFailure=False)
        yield self.processStep(step)

        step = ShellCommand(
            name='filter coverage',
            command=self.envCmd.split() + ['lcov',
                '--remove', 'opencv_total.info',
                '/usr/include/*',
                '/usr/lib/*',
                '/usr/local/include/*',
                '*/opencv/apps/*',
                '*/opencv/samples/*',
                '*/opencv/3rdparty/*',
                '*/opencv/modules/ts/*',
                '*/opencv/modules/*/perf/*',
                '*/opencv/modules/*/test/*',
                '*/opencv/modules/*/samples/*',
                '*/build/modules/java_bindings_generator/*',
                '*/build/modules/python_bindings_generator/*',
                '*/opencv_contrib/modules/*/perf/*',
                '*/opencv_contrib/modules/*/test/*',
                '*/opencv_contrib/modules/*/samples/*',
                '*/opencv/*' if self.isContrib else '*/opencv_contrib/*',
                '-o', 'opencv_filtered.info'],
            workdir='build',
            env=self.env,
            haltOnFailure=False)
        yield self.processStep(step)

        @renderer
        def genTitle(props):
            desc = props.getProperty('commit-description')
            res = []
            if isinstance(desc, dict):
                for n,k in [('OpenCV', 'opencv'), ('Contrib', 'opencv_contrib'), ('Extra', 'opencv_extra')]:
                    if k in desc:
                        res.append('%s: %s' % (n,desc[k]))
            else:
                res.append(str(desc))
            return ' / '.join(res)

        step = GenHTML(
            name='generate coverage report',
            command=self.envCmd.split() + ['genhtml',
                '--prefix', Interpolate('%(prop:builddir)s'),
                '-t', genTitle,
                '-o', 'coverage_html',
                'opencv_filtered.info'],
            workdir='build',
            env=self.env
            )
        yield self.processStep(step)

        path = 'opencv_releases/%(prop:buildername)s/%(prop:timestamp)s_%(prop:buildnumber)s/coverage_html'
        step = DirectoryUpload(
                name='upload coverage',
                workdir='build',
                slavesrc='coverage_html',
                masterdest=Interpolate(getExportDirectory() + path),
                url=Interpolate(getExportURL() + path + '/index.html'))
        yield self.processStep(step)
