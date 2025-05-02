#!/bin/bash

# 1. Remove old installations
apt-get remove -y msodbcsql17 msodbcsql18 unixodbc
rm -rf /etc/apt/sources.list.d/mssql-release.list

# 2. Install dependencies
apt-get update
apt-get install -y curl gnupg debconf-utils

# 3. Add Microsoft repository
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list
apt-get update

# 4. Install the driver (FORCE non-interactive setup)
export DEBIAN_FRONTEND=noninteractive
ACCEPT_EULA=Y apt-get install -y msodbcsql18
apt-get install -y unixodbc-dev

# 5. Verify the driver files exist
ls -l /opt/microsoft/msodbcsql18/lib64/libmsodbcsql-18.*.so

# 6. Start your app
gunicorn --bind=0.0.0.0:8000 --timeout 600 api.routes:app