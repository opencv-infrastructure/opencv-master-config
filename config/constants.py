slave = {  # buildslave passwords are stored in the other place
    'linux-slave-x64' : { 'max_builds' : 1, 'properties' : { 'CPUs' : 3, 'parallel_tests' : 3 } },
    'linux-slave-x64-2' : { 'max_builds' : 1, 'properties' : { 'CPUs' : 3, 'parallel_tests' : 3 } },
    'linux-slave-x64-3' : { 'max_builds' : 1, 'properties' : { 'CPUs' : 3, 'parallel_tests' : 3 } },
    'windows-slave-x64-1' : { 'max_builds' : 2, 'properties' : { 'CPUs' : 4, 'parallel_tests' : 3 } },
    'windows-slave-x64-2' : { 'max_builds' : 2, 'properties' : { 'CPUs' : 4, 'parallel_tests' : 3 } },
    'windows-slave-x64-intel' : { 'max_builds' : 4, 'properties' : { 'CPUs' : 4, 'parallel_tests' : 3 } },
    'macosx-slave' : { 'max_builds' : 2, 'properties' : { 'CPUs' : 4, 'parallel_tests' : 3 } },
    'macosx-slave-2' : { 'max_builds' : 1, 'properties' : { 'CPUs' : 4, 'parallel_tests' : 3 } },
    'macosx-slave-3' : { 'max_builds' : 1, 'properties' : { 'CPUs' : 4, 'parallel_tests' : 3 } },
}

PLATFORM_DEFAULT = 'default'
PLATFORM_INTEL = 'broadwell'

# Git mirror repository
URL_GIT_BASE = r'git://code.ocv/'
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

import os
if os.environ.get('DEBUG_HOST', None) == '':
    del os.environ['DEBUG_HOST']
if os.environ.get('DEBUG_PORT', None) == '':
    del os.environ['DEBUG_PORT']
DEBUG_HOST = os.environ.get('DEBUG_HOST', '172.17.42.1')
DEBUG_PORT = int(os.environ.get('DEBUG_PORT', '5678'))
DEBUG_SUSPEND = bool(os.environ.get('DEBUG_SUSPEND', 'False'))
DEBUG_URL = 'dev_enable_debug'
