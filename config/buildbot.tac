
import os

from twisted.application import service
from buildbot.master import BuildMaster

basedir = '.'
rotateLength = 1000000
maxRotatedFiles = 10
configfile = 'master.py'

# Default umask for server
umask = 0002

# if this is a relocatable tac file, get the directory containing the TAC
if basedir == '.':
    import os.path
    basedir = os.path.abspath(os.path.dirname(__file__))

# note: this line is matched against to check that this is a buildmaster
# directory; do not edit it.
application = service.Application('buildmaster')
from twisted.python.logfile import LogFile
from twisted.python.log import ILogObserver, FileLogObserver
logfile = LogFile.fromFullPath(os.path.join('/data/logs', "twistd.log"), rotateLength=rotateLength,
                                maxRotatedFiles=maxRotatedFiles)
application.setComponent(ILogObserver, FileLogObserver(logfile).emit)

m = BuildMaster(basedir, configfile, umask)
m.setServiceParent(application)
m.log_rotation.rotateLength = rotateLength
m.log_rotation.maxRotatedFiles = maxRotatedFiles

os.umask(0)

import sys, os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from pullrequest.service import PullRequestsService
import pr_github_opencv
pr = PullRequestsService(context=pr_github_opencv.context)
pr.setServiceParent(m)

import pr_github_opencv_contrib
pr = PullRequestsService(context=pr_github_opencv_contrib.context)
pr.setServiceParent(m)
