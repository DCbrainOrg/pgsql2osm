#!/bin/bash

# Pgsql2osm process script
# DCbrain - Francois Lacombe
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
configFile=$scriptDir/config.json
outputFile=$scriptDir/output.osm

# Paramètres
while [ ! $# -eq 0 ]
do
	case "$1" in
		--help | -h)
			echo "Use this syntax: pgsql2osm.sh -c <config_file.json> -o <output_file.osm>"
			echo "    -d: DB name"
			echo "    -c: Config file path"
			echo "    -o: Output file path"
			exit
			;;
		-c)
			configFile=$2
			;;
		-d)
			dbName=$2
			;;
		-o)
			outputFile=$(realpath $2)
			;;
	esac
	shift
done

# Recuperation config
[ -z $dbName ] && echo "Please provide db name with -d argument." && exit 3;

if [ -f $sconfigFile ]; then
  config_str=$(<"$configFile")
else
  echo "The config file provided doensn't exist"
  exit 2
fi

osmNodesTable=$(jq -r ".output_nodes" <<< ${config_str})
osmWaysTable=$(jq -r ".output_ways" <<< ${config_str})
osmWaysNodesTable=$(jq -r ".output_waysnodes" <<< ${config_str})

# Random 3 digit number for temporary sql tables
random_token=$(cat /dev/urandom | tr -dc '0-9' | fold -w 256 | head -n 1 | sed -e 's/^0*//' | head --bytes 3)
if [ "$random_token" == "" ]; then
  random_token=0
fi

psql -d $dbName \
    -v table_input_ways="$(jq -r ".input_ways" <<< ${config_str})" \
    -v table_input_nodes="$(jq -r ".input_nodes" <<< ${config_str})" \
    -v table_osm_nodes="$osmNodesTable" \
    -v table_osm_ways="$osmWaysTable" \
    -v table_osm_waysnodes="$osmWaysNodesTable" \
    -v resol=$(jq -r ".coordinates_resolution" <<< ${config_str}) \
    -v prime=$(jq -r ".coordinates_prime" <<< ${config_str}) \
	-v token="$random_token" \
    -f $scriptDir/toOsm.sql
	  
[[ -f $outputFile ]] && rm $outputFile

python3 $scriptDir/convert2osm.py $dbName $osmNodesTable $osmWaysTable $osmWaysNodesTable $outputFile