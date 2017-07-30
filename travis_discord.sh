#!/usr/bin/env bash

# from https://github.com/MaT1g3R/travis_discord with a fixed shebang

repo=""
if [ ! -z "$TRAVIS_REPO_SLUG" -a "$TRAVIS_REPO_SLUG" != " " ]; then
  repo="https://github.com/${TRAVIS_REPO_SLUG}"
fi

des="Build triggered by **${TRAVIS_EVENT_TYPE}**"
if [ ! -z "$TRAVIS_COMMIT" -a "$TRAVIS_COMMIT" != " " ]; then
  des+=" on [commit](${repo}/commit/${TRAVIS_COMMIT})"
fi

noun="failed"
color="16711680"
if [ "$TRAVIS_TEST_RESULT" == "0" ]; then
  noun="succeeded"
  color="1466533"
fi

title="${TRAVIS_REPO_SLUG} Travis CI build #${TRAVIS_BUILD_NUMBER} **${noun}**"

res="{\"embeds\": [{\"title\": \"${title}\", \"color\": ${color}, \"description\": \"${des}\", \"url\": \"${BUILD_URL}/${TRAVIS_BUILD_ID}\""

fields=""
if [ ! -z "$TRAVIS_BRANCH" -a "$TRAVIS_BRANCH" != " " ]; then
  fields+="{\"name\": \"Branch\", \"value\": \"${TRAVIS_BRANCH}\", \"inline\": true},"
fi

if [ ! -z "$TRAVIS_COMMIT_MESSAGE" -a "$TRAVIS_COMMIT_MESSAGE" != " " ]; then
  fields+="{\"name\": \"Commit Message\", \"value\": \"${TRAVIS_COMMIT_MESSAGE}\", \"inline\": true},"
fi

if [ ! -z "$repo" -a "$repo" != " " ]; then
  fields+="{\"name\": \"Repo\", \"value\": \"${repo}\", \"inline\": true},"
fi

if [ ! -z "$TRAVIS_PULL_REQUEST" -a "$TRAVIS_PULL_REQUEST" != " " -a "$TRAVIS_PULL_REQUEST" != "false" ]; then
  fields+="{\"name\": \"Pull Request\", \"value\": \"${TRAVIS_PULL_REQUEST}\", \"inline\": false},"
  if [ ! -z "$TRAVIS_PULL_REQUEST_BRANCH" -a "$TRAVIS_PULL_REQUEST_BRANCH" != " " ]; then
    fields+="{\"name\", \"Pull Request Branch\", \"value\": \"${TRAVIS_PULL_REQUEST_BRANCH}\", \"inline\": true},"
  fi

  if [ ! -z "$TRAVIS_PULL_REQUEST_SLUG" -a "$TRAVIS_PULL_REQUEST_SLUG" != " " ]; then
    fields+="{\"name\", \"Pull Request Repo\", \"value\": \"[PR Repo](https://github.com/${TRAVIS_PULL_REQUEST_SLUG})\", \"inline\": true},"
  fi
fi

if [[ $fields == *, ]]; then
  fields=${fields: : -1}
fi

if [ ! -z "$fields" -a "$fields" != " " ]; then
  res+=", \"fields\": [${fields}]"
fi
res+="}]}"
echo $res > res.json
curl -X POST -H "Content-Type: application/json" -d @res.json $DISCORD_WEBHOOK
