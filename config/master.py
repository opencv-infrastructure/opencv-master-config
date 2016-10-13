# -*- python -*-
# ex: set syntax=python:
import os

import constants

from twisted.web.static import File

from build_utils import getExportDirectory

c = BuildmasterConfig = {}

####### Some Options #######

c['projectName'] = "Open Source Computer Vision Library"
c['projectURL']  = "http://opencv.org"
c['buildbotURL'] = "http://localhost:8010/"
c['db_url'] = "sqlite:////data/db/state.sqlite"
c['slavePortnum'] = 9989
c['buildCacheSize'] = 50

c['buildHorizon'] = 500
c['logHorizon'] = 100
c['eventHorizon'] = 50

####### Main config #######

import project_builders

c['status'] = []
c['slaves'] = project_builders.slaves
c['builders'] = project_builders.builders
c['schedulers'] = project_builders.schedulers

####### Web GUI ########

from pullrequest.account import Authz

authz_cfg = Authz(
    # change any of these to True to enable; see the manual for more
    # options
    fileName=os.path.join('/etc/buildbot/htpasswd'),
    default_action='auth',
    prRestartBuild='auth',
    prStopBuild='auth',
    prRevertBuild=False,
    prShowPerf=False,
)

from pullrequest.webstatus import WebStatus

import pr_github_opencv
import pr_github_opencv_contrib

webstatus = WebStatus(http_port=8010, authz=authz_cfg, pullrequests=[pr_github_opencv.context, pr_github_opencv_contrib.context])
c['status'].append(webstatus)

webstatus.putChild('export', File(getExportDirectory()));

for b in c['builders']:
    if type(b) == type({}):
        b['builddir'] = '/builds/' + b['builddir']
    else:
        b.builddir = '/builds/' + b.builddir
