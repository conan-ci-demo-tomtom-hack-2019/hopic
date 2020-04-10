
/*
 * Copyright (c) 2019 - 2020 TomTom N.V. (https://tomtom.com)
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

def version = 'release/1'
@NonCPS
String transform_ssh_to_https(String url)
{
  // Rewrite SSH URLs to HTTP URLs, assuming that we don't need authentication
  def m = url =~ /^ssh:\/\/(?:\w+@)?(\w+(?:\.\w+)*\.?)(?::\d+)?\/(.+)$/
  if (!m) {
    m = url =~ /^(?:\w+@)?(\w+(?:\.\w+)*\.?):(.+)$/
  }
  m.each { match ->
    url = "https://${match[1]}/scm/${match[2]}"
  }
  return url
}
def repo = transform_ssh_to_https(scm.userRemoteConfigs[0].url.split('/')[0..-2].join('/') + '/hopic.git')

library(
    identifier: "cidriver@${version}",
    retriever: modernSCM([
        $class: 'GitSCMSource',
        remote: repo
  ]))
def cidriver = getCiDriver("git+${repo}@${version}")

pipeline {
  agent none

  triggers {
    // trigger build as AUTO_MERGE each 2 hours, on master and release branches only
    parameterizedCron(BRANCH_NAME =~ /^master$|^release\/\d+(?:\.\d+)?$/ ? '0 */2 * * * % MODALITY=AUTO_MERGE' : '')
  }

  parameters {
    choice(name:        'HOPIC_VERBOSITY',
           choices:      ['INFO', 'DEBUG'],
           description:  'Verbosity level to execute Hopic at.')
    choice(name:         'GIT_VERBOSITY',
           choices:      ['INFO', 'DEBUG'],
           description:  'Verbosity level to execute Git commands at.')
    choice(name: 'MODALITY',
           choices: 'NORMAL\nAUTO_MERGE',
           description: 'Modality of this execution of the pipeline.')
    booleanParam(defaultValue: false,
                 description: 'Clean build',
                 name: 'CLEAN')
  }

  options {
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 10, unit: 'MINUTES')
  }

  stages {
    stage("Commit Stage") {
      steps {
        script {
          cidriver.build(
            clean: params.CLEAN || params.MODALITY != "NORMAL",
          )
        }
      }
    }
  }
}
