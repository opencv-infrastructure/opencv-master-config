worker = {  # worker passwords are stored in the other place
    'linux-1' : { 'max_builds' : 2, 'properties' : { 'CPUs' : 4, 'parallel_tests-default' : 3 } },
    'linux-2' : { 'max_builds' : 1, 'properties' : { 'CPUs' : 4, 'parallel_tests-default' : 3 } },
    'linux-3' : { 'max_builds' : 2, 'properties' : { 'CPUs' : 4, 'parallel_tests-default' : 4 } },
    'linux-4' : { 'max_builds' : 2, 'properties' : { 'CPUs' : 4, 'parallel_tests-default' : 3 } },
    'linux-5' : { 'max_builds' : 2, 'properties' : { 'CPUs' : 4, 'parallel_tests-default' : 4 } },
    'windows-1' : { 'max_builds' : 2, 'properties' : { 'CPUs' : 4, 'parallel_tests-default' : 3 } },
    'windows-2' : { 'max_builds' : 2, 'properties' : { 'CPUs' : 4, 'parallel_tests-default' : 3 } },
    'macosx-1' : { 'max_builds' : 1, 'properties' : { 'CPUs' : 4, 'parallel_tests-default' : 3 } },
    'macosx-2' : { 'max_builds' : 1, 'properties' : { 'CPUs' : 4, 'parallel_tests-default' : 3 } },

    'windows-pack' : { 'max_builds' : 1, 'properties' : { 'CPUs' : 1, 'parallel_tests' : 1 } },
}

PLATFORM_ANY = 'any'
PLATFORM_DEFAULT = 'default'
PLATFORM_SKYLAKE = 'skl'
PLATFORM_SKYLAKE_X = 'skx'  # with AVX512

# Git mirror repository
URL_GIT_BASE = r'git://code.ocv/opencv/'
URL_OPENCV = URL_GIT_BASE + r'opencv.git'
URL_OPENCV_EXT = URL_GIT_BASE + r'opencv_extra.git'
URL_OPENCV_CONTRIB = URL_GIT_BASE + r'opencv_contrib.git'

repos = {
    URL_OPENCV: 'opencv',
    URL_OPENCV_EXT: 'opencv_extra',
    URL_OPENCV_CONTRIB: 'opencv_contrib',
}

class CodeBase:
    def __init__(self, branch):
        self.branch = branch

    def getCodebase(self):
        result = dict()
        result['opencv'] = { 'repository': URL_OPENCV, 'branch': self.branch}
        result['opencv_extra'] = { 'repository': URL_OPENCV_EXT, 'branch': self.branch}
        result['opencv_contrib'] = { 'repository': URL_OPENCV_CONTRIB, 'branch': self.branch}
        return result

codebase = { }
codebase['master'] = CodeBase('master')
codebase['2.4'] = CodeBase('2.4')
codebase['3.4'] = CodeBase('3.4')
codebase['branch'] = CodeBase('master')

import re

def trace(s):
    print s

def params_without_passwords(params):
    safe_params = params.copy()
    for i in safe_params:
        if re.match(r'.*(pwd|pass|password|login|user).*', i):
            safe_params[i] = "*****"
    return safe_params
