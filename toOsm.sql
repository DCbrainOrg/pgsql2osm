\timing on
-- ########
-- pgsql2osm
-- Convert Postgis geometries to topological objects
-- François Lacombe - DCbrain
--
-- Variables
-- :table_input_ways Input table for ways
-- :table_input_nodes Input table for nodes (if any)
-- :table_osm_nodes Output table for nodes
-- :table_osm_ways Output table for ways
-- :table_osm_waysnodes Output table linking nodes and ways
-- :resol Coordinates resolution
-- :prime Prime number (> :resol) as to get hashcode from coordinates
-- ########

-- Drop existing tables
drop table if exists :table_osm_nodes;
drop table if exists :table_osm_ways;
drop table if exists :table_osm_waysnodes;
DROP TABLE if exists local_nodes_:token;

-- Create output tables
create table :table_osm_nodes (osrm_node_id bigint not null, node geometry, tags jsonb, abscisse double precision, ordonnee double precision);
create table :table_osm_ways (osrm_way_id bigint not null, arc_uuid UUID, geom geometry, tags jsonb);
create table :table_osm_waysnodes (osrm_way_id bigint not null, osrm_node_id bigint not null, arc_uuid UUID, position int not null, node geometry);

-- Simple copy of edges with optional osm_id, uuid, tags and geometry
INSERT INTO :table_osm_ways (osrm_way_id, arc_uuid, tags, geom)
    SELECT
        ua.osm_id,
        arc_uuid,
        COALESCE(tags,'{}')::jsonb AS tags,
        geom
    FROM :table_input_ways ua;

ALTER TABLE :table_osm_ways ADD PRIMARY KEY (osrm_way_id);

create index on :table_osm_ways using btree(osrm_way_id);
create index on :table_osm_ways using btree(arc_uuid);
create index on :table_osm_ways using btree(tags);

-- Dump points of ways in a temporary local table
create table local_nodes_:token (arc_uuid UUID, dp geometry_dump);
INSERT INTO local_nodes_:token (arc_uuid, dp) select ua.arc_uuid AS arc_uuid, ST_dumpPoints(ua.geom) AS dp from :table_input_ways ua;
CREATE INDEX ON local_nodes_:token USING btree(dp);
CREATE INDEX ON local_nodes_:token USING btree(arc_uuid);

-- Populate waysnodes table with direct node_id calculation out of hashcode of coordinates
WITH nodes AS (
    SELECT
        ow.osrm_way_id AS osrm_way_id,
        topo.arc_uuid AS arc_uuid,
        round(ST_X(ST_setSRID((topo.dp).geom,4326))::numeric,:resol)*1000000+:prime AS lng,
        round(ST_Y(ST_setSRID((topo.dp).geom,4326))::numeric,:resol)*1000000 AS lat,
        ST_setSRID((topo.dp).geom,4326) as node,
        (topo.dp).path[1] AS position,
        CASE 
        WHEN (topo.dp).path[1]=1 THEN COALESCE ((ow.tags->>'pgsql2osm:layer:start')::integer, COALESCE((ow.tags->>'pgsql2osm:layer')::integer, 1))
        WHEN (topo.dp).path[1]>1 THEN COALESCE((ow.tags->>'pgsql2osm:layer')::integer, 1)
        END AS layer
    FROM local_nodes_:token topo
    join :table_osm_ways ow ON ow.arc_uuid=topo.arc_uuid
)
INSERT INTO :table_osm_waysnodes (osrm_way_id, arc_uuid, osrm_node_id, node, position)
    SELECT
        distinct nodes.osrm_way_id,
        nodes.arc_uuid,
        round((nodes.lat + (:prime*nodes.lng)) * nodes.layer) AS osrm_node_id,
        nodes.node,
        nodes.position
    FROM nodes;

ALTER TABLE :table_osm_waysnodes ADD PRIMARY KEY (osrm_way_id, osrm_node_id, position);
CREATE INDEX ON :table_osm_waysnodes using btree(osrm_node_id);
CREATE INDEX ON :table_osm_waysnodes USING btree(osrm_way_id);
CREATE INDEX ON :table_osm_waysnodes USING btree(position);

DROP TABLE local_nodes_:token;

-- Population of nodes table from waysnodes table.
-- No duplicate detection is required since hashcode give duplicates the same id
INSERT INTO :table_osm_nodes (osrm_node_id, node, abscisse, ordonnee)
    SELECT
        DISTINCT ON (own.osrm_node_id) osrm_node_id,
        own.node,
        ST_X(own.node),
        ST_Y(own.node)
    FROM :table_osm_waysnodes own 
ON CONFLICT DO NOTHING;

ALTER TABLE :table_osm_nodes ADD PRIMARY KEY (osrm_node_id);

CREATE INDEX ON :table_osm_nodes USING gist (node);
CREATE index on :table_osm_nodes using btree(osrm_node_id);

-- Update of nodes tags with eventual input node tables
update :table_osm_nodes osn
    set tags = COALESCE(osn.tags,'{}')::jsonb || COALESCE(un.tags,'{}')::jsonb
    FROM :table_input_nodes un
    WHERE round(ST_Y(un.geom)::numeric,:resol)*1000000 + :prime*(round(ST_X(un.geom)::numeric,:resol)*1000000+:prime)=osn.osrm_node_id;