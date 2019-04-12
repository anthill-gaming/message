#!/usr/bin/env bash

# Setup postgres database
createuser -d anthill_message -U postgres
createdb -U anthill_message anthill_message