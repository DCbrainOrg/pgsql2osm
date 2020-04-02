#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Postgresql topological twin to XML OSM converter
Created on Fri Mar  9 10:07:11 2018

@author: Maxime Beauchene - DCbrain
"""

import numpy as np
import os
import sys
import time
import datetime as dt
from multiprocessing import Pool, cpu_count

from pg import DB
from pgdb import connect
import logging

tab = '\t'
tab2 = '\t\t'

def printPuces(liste):
    """
    Function that print each element of a list with one tabulation and a dot 
    before.
     ---
    parameters :
        liste : python list.
    produces :
        print the list.
    """
    for e in liste :
        print(tab+'*',e)
        

def requestDB(requete='select * from ',tableName='planet_osm_line',base='champ',
    limit=None,only=False,verbose=False):
    """
    Function that execute an sql request into a postgres database.
     ---
    parameters :
        string requete : the request will be executed.
        string tableName : the name of the table will be request if only is false.
        string base : name of the database
        int limit : integer, request limit option.
    produces :
        string requeteResult : request result.
    """
    db = DB(dbname=base)
    
    if verbose :
        tablesList = db.get_tables()
        print('Tables :')
        printPuces(tablesList)
        print('\n')
        
        headerLinesOSM = db.get_attnames(tableName) 
        print('Table header :')
        printPuces(headerLinesOSM)
        print('\n')
    
    if only :
        requeteResult = db.query(requete).getresult()
    elif limit is None :
        requeteResult = db.query(requete+tableName).getresult()
    else :
        requeteResult = db.query(requete+tableName+' limit '+str(limit)).getresult()
    
    return requeteResult

def getNodeEntry(nodeId,lon,lat,tags):
    """
    Function that compute one node entry for the xml file.
     ---
    parameters :
        int nodeId : id of the node.
        float x : abcisse of the node.
        float y ; ordinate of the node.
        dict tags : node tags.
    produces :
        string node_entry : the node entry for xml file.
    """

    node_entry = ''
    if isinstance(tags,dict) :
        node_entry += tab+'<node id="'+str(nodeId)+'" lat="'+format(float(lat),".10f").rstrip('0').rstrip(".") \
                        +'" lon="'+format(float(lon),".10f").rstrip('0').rstrip(".")+'" user="pgsql2osm" uid="1" ' \
                        +'visible="true" version="1" ' \
                        +'changeset="1" timestamp="' \
                        +dt.datetime.now().isoformat().split('.')[0]+'Z'+'">\n'
        for k,v in tags.items() :
            if not str(v):
                continue
            node_entry += tab2+'<tag k="'+str(k)+'" v="' \
                          +str(v).replace('"','').replace('&','&amp').replace('<','&lt;')+'"/>\n'
        node_entry += tab+'</node>\n'
    else:
        node_entry += tab+'<node id="'+str(nodeId)+'" lat="'+format(float(lat),".10f").rstrip('0').rstrip(".") \
                        +'" lon="'+format(float(lon),".10f").rstrip('0').rstrip(".")+'" user="DCbrain" uid="1" ' \
                        +'visible="true" version="1" ' \
                        +'changeset="1" timestamp="' \
                        +dt.datetime.now().isoformat().split('.')[0]+'Z'+'"/>\n'
    return node_entry

def prepareNodeEntry(db_name,table,limit,offset) :
    """
    Function that compute nodes entries for the xml file, with cursor 
    request on part of the nodes table.
     ---
    parameters :
        string table : Table to use
        int limit : limit value for the cursor request.
        int offset : offset value for the cursor request.
    produces :
        string node_entry : the nodes entries for xml file.
    """
    node_entry = ''

    try :
        con = connect(database=db_name)
        curs = con.cursor()
        curs.execute('select osrm_node_id, jsonb_strip_nulls(tags), abscisse, ordonnee from '
                     +table+' order by osrm_node_id limit '
                     +str(limit)+' offset '+str(offset))
        
        keepGoing = True
        while keepGoing :
            try :
                nodeId, tags, x, y = curs.fetchone()
                try :
                    node_entry += getNodeEntry(nodeId,x,y,tags)
                except Exception as e :
                    logging.warning('ode ignore : '+str(nodeId)+', '+str(e))
            except :
                keepGoing = False           
                
        curs.close()
        con.close()
            
    except Exception as e :
        logging.warning('prepareNodeEntry : '+str(e))

    return node_entry

def writeNodes(db_name,table,OSMfile,n_jobs=cpu_count()-1) :
    """
    Function that write all nodes from nodes table into the xml file.
     ---
    parameters :
        string table : table name to use.
        file OSMfile : xml file.
        n_jobs : number of thread will be created.
    produces :
        write the nodes entries into xml file.
    """
    print('Start writting nodes to osm file...')
    logging.info('Start writting nodes to osm file...')

    nodesCount = requestDB(requete='select count(*) from ',
                               tableName=table,base=db_name)[0][0]
    
    print('There is',nodesCount,'nodes to write.')
    logging.info('There is '+str(nodesCount)+' nodes to write.')    
    
    cut_indexes = [int(c) for c in np.linspace(0,nodesCount,n_jobs+1)]
    params = []
    for i in range(len(cut_indexes)-1) :
        params.append([db_name,table,cut_indexes[i+1]-cut_indexes[i],cut_indexes[i]])
        
    pool = Pool(n_jobs)
    resultats = pool.starmap(prepareNodeEntry,params)
    for node_entry in resultats :
        if len(node_entry) > 0 :
            OSMfile.write(node_entry)        
    pool.terminate()
        
    del params
    del resultats

    print('Writting nodes to osm file done.')      
    logging.info('Writting nodes to osm file done.')
        


def getWayEntry(wayId,tags,wayNodes) :
    """
    Function that compute one way entry for the xml file.
     ---
    parameters :
        int wayId : id of the way.
        dict tags : way tags.
        list wayNodes : list of nodes belonging to the way.
    produces :
        string way_entry : the way entry for xml file.
    """

    way_entry = ''
    way_entry += tab+'<way id="'+str(wayId)+'" user="pgsql2osm" uid="1" ' \
                  +'visible="true" version="1" changeset="1" timestamp="' \
                  +dt.datetime.now().isoformat().split('.')[0]+'Z'+'">\n'

    for node in wayNodes :
        way_entry += tab2+'<nd ref="'+str(node)+'"/>\n'
    if isinstance(tags,dict) :
        for k,v in tags.items() :
            if not str(v):
                continue
            way_entry += tab2+'<tag k="'+str(k)+'" v="' \
                      +str(v).replace('"','').replace('&','&amp;').replace('<','&lt;')+'"/>\n'        

    way_entry += tab+'</way>\n'
    return way_entry


def prepareWayEntry(db_name,nodes_table,ways_table,waysnodes_table,limit,offset) :
    """
    Function that compute ways entries for the xml file, with cursor 
    request on part of the ways table.
     ---
    parameters :
        string nodes_table : nodes table name
        string ways_table : ways table name
        string waysnodes_table : ways nodes linkage table name
        int limit : limit value for the cursor request.
        int offset : offset value for the cursor request.
    produces :
        string way_entry : the ways entries for xml file.
    """
    way_entry = ''
  
    try :
        con = connect(database=db_name)
        curs = con.cursor()
        curs.execute('with ways as (select osrm_way_id, arc_uuid, jsonb_strip_nulls(tags) AS tags '
                     +'from '+ways_table+' order by osrm_way_id '
                     +'limit '+str(limit)+' offset '+str(offset)
                     +') select ways.osrm_way_id, '
                     +'ways.tags, nodes.osrm_node_id from ways JOIN '
                     +waysnodes_table+' own ON '
                     +'own.osrm_way_id=ways.osrm_way_id JOIN '
                     +nodes_table+' nodes ON '
                     +'nodes.osrm_node_id=own.osrm_node_id order by '
                     +'ways.osrm_way_id, own.position')

        
        keepGoing = True
        wayNodes = []
        wayId = None
        oldWayId = None
        oldTags = None
        while keepGoing :
            try :
                wayId, tags, node = curs.fetchone()
                
                if oldWayId != wayId and oldWayId is not None :
                    try :
                        way_entry += getWayEntry(oldWayId,oldTags,wayNodes)
                    except Exception as e :
                        logging.warning('way ignore : '+str(oldWayId)+', '+str(e))
                    wayNodes = []
                
                oldWayId = wayId
                oldTags = tags
                
                wayNodes.append(node)
                                    
            except :
                keepGoing = False
                
        try :
            if wayId is not None :
                way_entry += getWayEntry(wayId,tags,wayNodes)
        except Exception as e :
            logging.warning('way ignore : '+str(wayId)+', '+str(e))
                
        curs.close()
        con.close()    

    except Exception as e :
        logging.warning('prepareWayEntry : '+str(e))
        
    return way_entry


def writeWays(db_name,nodes_table,ways_table,waysnodes_table,OSMfile,n_jobs=cpu_count()-1) :
    """
    Function that write all ways from ways table into the xml file.
     ---
    parameters :
        string nodes_table : nodes table name
        string ways_table : ways table name
        string waysnodes_table : ways nodes linkage table name
        file OSMfile : xml file.
        n_jobs : number of thread will be created.
    produces :
        write the ways entries into xml file.
    """
    print('Start writting ways to osm file...')
    logging.info('Start writting ways to osm file...')
    
    waysCount = requestDB(requete='select count(*) from ',
                               tableName=ways_table,base=db_name)[0][0]
    
    print('There is',waysCount,'ways to write.')
    logging.info('There is '+str(waysCount)+' ways to write.')
    
    cut_indexes = [int(c) for c in np.linspace(0,waysCount,n_jobs+1)]
    params = []
    for i in range(len(cut_indexes)-1) :
        params.append([db_name,nodes_table,ways_table,waysnodes_table,cut_indexes[i+1]-cut_indexes[i],cut_indexes[i]])
    
    pool = Pool(n_jobs)
    resultats = pool.starmap(prepareWayEntry,params)
    for way_entry in resultats :
        if len(way_entry) > 0 :
            
            OSMfile.write(way_entry)

    pool.terminate()
    del params
    del resultats

    print('Writting ways to osm file done.') 
    logging.info('Writting ways to osm file done.')
    

if __name__ == '__main__':
    x=0
    
    if len(sys.argv) == 6 :
        start = time.time()
        db_name = sys.argv[1]
        nodes_table = sys.argv[2]
        ways_table = sys.argv[3]
        waysnodes_table = sys.argv[4]
        output_file = sys.argv[5]

        data_dir = os.path.dirname(output_file)

        logging.basicConfig(filename=data_dir+os.sep+'convert2osm.log',
                    format='[%(levelname)s] [%(asctime)s] %(message)s',
                    level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')

        if not os.path.exists(data_dir) :
            logging.error('Output directory doesn\'t exist')
            print('Output directory doesn\'t exist')
        
        print('Start extracting data from postgres...')
        logging.info('Start extracting data from postgres...')
        OSMfile = open(output_file,'w')
        OSMfile.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                    +'<osm version="0.6" generator="Pgsql2osm 0.1">\n'
                    +'\t<bounds minlat="42.532012" minlon="-4.845629" '
                    +'maxlat="51.811700" maxlon="9.241046"/>\n')    
        
        writeNodes(db_name,nodes_table,OSMfile)
        
        writeWays(db_name,nodes_table,ways_table,waysnodes_table,OSMfile)
        
        OSMfile.write('</osm>\n')
        OSMfile.close()
        
        print('Extraction done in ',time.time()-start,' seconds.')
        logging.info('Extraction done in '+str(time.time()-start)+' seconds.')
    else :
        print('Please use this script with 5 args like:\n' \
              +'python3 convert2osm.py db_name nodes_table ways_table ways_nodes_table output_path')
