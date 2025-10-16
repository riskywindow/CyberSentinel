"""Graph synchronization for knowledge base to Neo4j."""

import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from collections import defaultdict

from storage.neo4j.client import Neo4jClient
from knowledge.corpora.loaders import KnowledgeDocument, KnowledgeCorpus

logger = logging.getLogger(__name__)

class GraphSynchronizer:
    """Synchronizes knowledge base with Neo4j graph database."""
    
    def __init__(self, neo4j_client: Neo4jClient):
        self.neo4j_client = neo4j_client
    
    def sync_attack_to_graph(self, documents: List[KnowledgeDocument]) -> Dict[str, Any]:
        """Sync ATT&CK techniques and relationships to Neo4j."""
        
        logger.info("Syncing ATT&CK data to Neo4j graph...")
        
        attack_docs = [doc for doc in documents if doc.doc_type == "attack_technique"]
        
        if not attack_docs:
            logger.warning("No ATT&CK documents found to sync")
            return {"techniques_synced": 0, "relationships_created": 0}
        
        # Extract ATT&CK data
        attack_data = []
        tactic_relationships = []
        
        for doc in attack_docs:
            technique_id = doc.metadata.get("attack_id", doc.id)
            name = doc.title
            tactic = doc.metadata.get("tactic", "")
            platforms = doc.metadata.get("platforms", [])
            data_sources = doc.metadata.get("data_sources", [])
            
            attack_data.append({
                "id": technique_id,
                "name": name,
                "tactic": tactic,
                "platforms": platforms,
                "data_sources": data_sources,
                "description": self._extract_description(doc.content),
                "url": doc.url
            })
            
            if tactic:
                tactic_relationships.append((technique_id, tactic))
        
        # Sync to Neo4j
        stats = self._create_attack_graph(attack_data, tactic_relationships)
        
        logger.info(f"ATT&CK sync completed: {stats}")
        return stats
    
    def sync_cve_to_graph(self, documents: List[KnowledgeDocument]) -> Dict[str, Any]:
        """Sync CVE vulnerabilities to Neo4j."""
        
        logger.info("Syncing CVE data to Neo4j graph...")
        
        cve_docs = [doc for doc in documents if doc.doc_type == "cve"]
        
        if not cve_docs:
            logger.warning("No CVE documents found to sync")
            return {"cves_synced": 0, "product_relationships": 0}
        
        cve_data = []
        product_relationships = []
        
        for doc in cve_docs:
            cve_id = doc.metadata.get("cve_id", doc.id)
            cvss_score = doc.metadata.get("cvss_score", 0.0)
            cwe = doc.metadata.get("cwe", "")
            affected_products = doc.metadata.get("affected_products", [])
            published = doc.metadata.get("published", "")
            
            cve_data.append({
                "id": cve_id,
                "description": self._extract_description(doc.content),
                "cvss_score": cvss_score,
                "cwe": cwe,
                "published": published,
                "url": doc.url
            })
            
            # Create relationships to affected products
            for product in affected_products:
                product_relationships.append((cve_id, product))
        
        stats = self._create_cve_graph(cve_data, product_relationships)
        
        logger.info(f"CVE sync completed: {stats}")
        return stats
    
    def sync_sigma_to_graph(self, documents: List[KnowledgeDocument]) -> Dict[str, Any]:
        """Sync Sigma detection rules to Neo4j."""
        
        logger.info("Syncing Sigma rules to Neo4j graph...")
        
        sigma_docs = [doc for doc in documents if doc.doc_type == "sigma_rule"]
        
        if not sigma_docs:
            logger.warning("No Sigma documents found to sync")
            return {"rules_synced": 0, "technique_relationships": 0}
        
        rule_data = []
        technique_relationships = []
        
        for doc in sigma_docs:
            rule_id = doc.metadata.get("rule_id", doc.id)
            level = doc.metadata.get("level", "medium")
            author = doc.metadata.get("author", "")
            tags = doc.metadata.get("tags", [])
            logsource = doc.metadata.get("logsource", {})
            attack_techniques = doc.metadata.get("attack_techniques", [])
            
            rule_data.append({
                "id": rule_id,
                "title": doc.title,
                "description": self._extract_description(doc.content),
                "level": level,
                "author": author,
                "tags": tags,
                "logsource_product": logsource.get("product", ""),
                "logsource_service": logsource.get("service", ""),
                "logsource_category": logsource.get("category", "")
            })
            
            # Create relationships to ATT&CK techniques
            for technique in attack_techniques:
                technique_id = technique.upper()
                if technique_id.startswith('T'):
                    technique_relationships.append((rule_id, technique_id))
        
        stats = self._create_sigma_graph(rule_data, technique_relationships)
        
        logger.info(f"Sigma sync completed: {stats}")
        return stats
    
    def create_knowledge_graph_relationships(self) -> Dict[str, Any]:
        """Create cross-domain relationships in the knowledge graph."""
        
        logger.info("Creating cross-domain knowledge graph relationships...")
        
        relationships_created = 0
        
        try:
            with self.neo4j_client.driver.session() as session:
                # 1. Connect Sigma rules to CVEs based on affected products
                query1 = """
                MATCH (rule:SigmaRule), (cve:CVE), (product:Product)
                WHERE (cve)-[:AFFECTS]->(product) 
                AND (rule.logsource_product CONTAINS toLower(product.name) 
                     OR toLower(rule.description) CONTAINS toLower(product.name))
                MERGE (rule)-[:DETECTS_VULNERABILITY]->(cve)
                RETURN count(*) as created
                """
                result1 = session.run(query1)
                relationships_created += result1.single()["created"]
                
                # 2. Connect CVEs to ATT&CK techniques based on common exploitation patterns
                query2 = """
                MATCH (cve:CVE), (ttp:TTP)
                WHERE toLower(cve.description) CONTAINS 'remote code execution'
                AND ttp.technique_id IN ['T1190', 'T1203', 'T1210']
                MERGE (cve)-[:ENABLES_TECHNIQUE]->(ttp)
                RETURN count(*) as created
                """
                result2 = session.run(query2)
                relationships_created += result2.single()["created"]
                
                # 3. Create mitigation relationships
                query3 = """
                MATCH (rule:SigmaRule)-[:DETECTS]->(ttp:TTP)
                MERGE (rule)-[:MITIGATES]->(ttp)
                RETURN count(*) as created
                """
                result3 = session.run(query3)
                relationships_created += result3.single()["created"]
        
        except Exception as e:
            logger.error(f"Failed to create cross-domain relationships: {e}")
            return {"error": str(e), "relationships_created": 0}
        
        stats = {"relationships_created": relationships_created}
        logger.info(f"Cross-domain relationships created: {stats}")
        return stats
    
    def _create_attack_graph(self, attack_data: List[Dict[str, Any]], 
                           tactic_relationships: List[Tuple[str, str]]) -> Dict[str, Any]:
        """Create ATT&CK technique and tactic nodes with relationships."""
        
        techniques_created = 0
        tactics_created = 0
        relationships_created = 0
        
        try:
            with self.neo4j_client.driver.session() as session:
                # Create technique nodes
                for technique in attack_data:
                    session.run(
                        """
                        MERGE (t:TTP {id: $id})
                        SET t.technique_id = $id,
                            t.name = $name,
                            t.tactic = $tactic,
                            t.platforms = $platforms,
                            t.data_sources = $data_sources,
                            t.description = $description,
                            t.url = $url,
                            t.node_type = 'technique'
                        """,
                        **technique
                    )
                    techniques_created += 1
                
                # Create tactic nodes and relationships
                unique_tactics = set(tactic for _, tactic in tactic_relationships if tactic)
                for tactic in unique_tactics:
                    session.run(
                        "MERGE (tac:Tactic {name: $tactic}) SET tac.node_type = 'tactic'",
                        tactic=tactic
                    )
                    tactics_created += 1
                
                # Create technique -> tactic relationships
                for technique_id, tactic in tactic_relationships:
                    if tactic:
                        session.run(
                            """
                            MATCH (t:TTP {id: $technique_id})
                            MATCH (tac:Tactic {name: $tactic})
                            MERGE (t)-[:PART_OF]->(tac)
                            """,
                            technique_id=technique_id, tactic=tactic
                        )
                        relationships_created += 1
        
        except Exception as e:
            logger.error(f"Failed to create ATT&CK graph: {e}")
            raise
        
        return {
            "techniques_synced": techniques_created,
            "tactics_created": tactics_created,
            "relationships_created": relationships_created
        }
    
    def _create_cve_graph(self, cve_data: List[Dict[str, Any]], 
                         product_relationships: List[Tuple[str, str]]) -> Dict[str, Any]:
        """Create CVE and product nodes with relationships."""
        
        cves_created = 0
        products_created = 0
        relationships_created = 0
        
        try:
            with self.neo4j_client.driver.session() as session:
                # Create CVE nodes
                for cve in cve_data:
                    session.run(
                        """
                        MERGE (c:CVE {id: $id})
                        SET c.cve_id = $id,
                            c.description = $description,
                            c.cvss_score = $cvss_score,
                            c.cwe = $cwe,
                            c.published = $published,
                            c.url = $url,
                            c.node_type = 'vulnerability'
                        """,
                        **cve
                    )
                    cves_created += 1
                
                # Create product nodes and relationships
                unique_products = set(product for _, product in product_relationships)
                for product in unique_products:
                    session.run(
                        """
                        MERGE (p:Product {name: $product})
                        SET p.node_type = 'product'
                        """,
                        product=product
                    )
                    products_created += 1
                
                # Create CVE -> product relationships
                for cve_id, product in product_relationships:
                    session.run(
                        """
                        MATCH (c:CVE {id: $cve_id})
                        MATCH (p:Product {name: $product})
                        MERGE (c)-[:AFFECTS]->(p)
                        """,
                        cve_id=cve_id, product=product
                    )
                    relationships_created += 1
        
        except Exception as e:
            logger.error(f"Failed to create CVE graph: {e}")
            raise
        
        return {
            "cves_synced": cves_created,
            "products_created": products_created,
            "product_relationships": relationships_created
        }
    
    def _create_sigma_graph(self, rule_data: List[Dict[str, Any]], 
                          technique_relationships: List[Tuple[str, str]]) -> Dict[str, Any]:
        """Create Sigma rule nodes with relationships to ATT&CK techniques."""
        
        rules_created = 0
        relationships_created = 0
        
        try:
            with self.neo4j_client.driver.session() as session:
                # Create Sigma rule nodes
                for rule in rule_data:
                    session.run(
                        """
                        MERGE (r:SigmaRule {id: $id})
                        SET r.rule_id = $id,
                            r.title = $title,
                            r.description = $description,
                            r.level = $level,
                            r.author = $author,
                            r.tags = $tags,
                            r.logsource_product = $logsource_product,
                            r.logsource_service = $logsource_service,
                            r.logsource_category = $logsource_category,
                            r.node_type = 'detection_rule'
                        """,
                        **rule
                    )
                    rules_created += 1
                
                # Create relationships to ATT&CK techniques
                for rule_id, technique_id in technique_relationships:
                    session.run(
                        """
                        MATCH (r:SigmaRule {id: $rule_id})
                        MATCH (t:TTP {id: $technique_id})
                        MERGE (r)-[:DETECTS]->(t)
                        """,
                        rule_id=rule_id, technique_id=technique_id
                    )
                    relationships_created += 1
        
        except Exception as e:
            logger.error(f"Failed to create Sigma graph: {e}")
            raise
        
        return {
            "rules_synced": rules_created,
            "technique_relationships": relationships_created
        }
    
    def _extract_description(self, content: str) -> str:
        """Extract description from document content."""
        lines = content.split('\n')
        description_lines = []
        
        for line in lines:
            line = line.strip()
            if line and not line.endswith(':') and len(line) > 20:
                description_lines.append(line)
                if len(description_lines) >= 3:  # Limit description length
                    break
        
        return ' '.join(description_lines)[:500]  # Limit to 500 chars

class KnowledgeGraphManager:
    """High-level manager for knowledge graph operations."""
    
    def __init__(self, neo4j_client: Neo4jClient):
        self.neo4j_client = neo4j_client
        self.synchronizer = GraphSynchronizer(neo4j_client)
        self.corpus = KnowledgeCorpus()
    
    def build_knowledge_graph(self) -> Dict[str, Any]:
        """Build the complete knowledge graph from all sources."""
        
        logger.info("Building knowledge graph...")
        
        # Load all knowledge documents
        documents = self.corpus.load_all_demo_slices()
        
        total_stats = {
            "total_documents": len(documents),
            "attack_stats": {},
            "cve_stats": {},
            "sigma_stats": {},
            "cross_domain_stats": {},
            "errors": []
        }
        
        try:
            # Sync ATT&CK data
            total_stats["attack_stats"] = self.synchronizer.sync_attack_to_graph(documents)
            
            # Sync CVE data
            total_stats["cve_stats"] = self.synchronizer.sync_cve_to_graph(documents)
            
            # Sync Sigma rules
            total_stats["sigma_stats"] = self.synchronizer.sync_sigma_to_graph(documents)
            
            # Create cross-domain relationships
            total_stats["cross_domain_stats"] = self.synchronizer.create_knowledge_graph_relationships()
            
        except Exception as e:
            error_msg = f"Knowledge graph build failed: {e}"
            logger.error(error_msg)
            total_stats["errors"].append(error_msg)
        
        logger.info(f"Knowledge graph build completed: {total_stats}")
        return total_stats
    
    def get_graph_statistics(self) -> Dict[str, Any]:
        """Get statistics about the knowledge graph."""
        
        stats = {}
        
        try:
            with self.neo4j_client.driver.session() as session:
                # Count nodes by type
                node_counts = session.run(
                    "MATCH (n) RETURN labels(n)[0] as label, count(n) as count"
                ).data()
                
                stats["node_counts"] = {item["label"]: item["count"] for item in node_counts}
                
                # Count relationships by type
                rel_counts = session.run(
                    "MATCH ()-[r]->() RETURN type(r) as rel_type, count(r) as count"
                ).data()
                
                stats["relationship_counts"] = {item["rel_type"]: item["count"] for item in rel_counts}
                
                # Total counts
                total_nodes = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
                total_rels = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
                
                stats["totals"] = {
                    "nodes": total_nodes,
                    "relationships": total_rels
                }
        
        except Exception as e:
            logger.error(f"Failed to get graph statistics: {e}")
            stats["error"] = str(e)
        
        return stats
    
    def query_attack_chain(self, start_technique: str, max_depth: int = 3) -> List[Dict[str, Any]]:
        """Query for potential attack chains starting from a technique."""
        
        try:
            with self.neo4j_client.driver.session() as session:
                result = session.run(
                    """
                    MATCH path = (start:TTP {technique_id: $start_technique})-[:PART_OF*0..1]->(tactic:Tactic)<-[:PART_OF*0..1]-(related:TTP)
                    WHERE start <> related
                    RETURN related.technique_id as technique_id, 
                           related.name as name,
                           related.tactic as tactic,
                           length(path) as distance
                    ORDER BY distance, related.technique_id
                    LIMIT 10
                    """,
                    start_technique=start_technique
                )
                
                return [dict(record) for record in result]
        
        except Exception as e:
            logger.error(f"Failed to query attack chain: {e}")
            return []
    
    def query_detection_coverage(self, technique_id: str) -> Dict[str, Any]:
        """Query detection coverage for a specific technique."""
        
        try:
            with self.neo4j_client.driver.session() as session:
                result = session.run(
                    """
                    MATCH (ttp:TTP {technique_id: $technique_id})
                    OPTIONAL MATCH (rule:SigmaRule)-[:DETECTS]->(ttp)
                    RETURN ttp.name as technique_name,
                           ttp.tactic as tactic,
                           collect(rule.title) as detection_rules,
                           count(rule) as rule_count
                    """,
                    technique_id=technique_id
                )
                
                record = result.single()
                if record:
                    return dict(record)
                else:
                    return {"error": f"Technique {technique_id} not found"}
        
        except Exception as e:
            logger.error(f"Failed to query detection coverage: {e}")
            return {"error": str(e)}