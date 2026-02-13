"""Knowledge corpus loaders for ATT&CK, CVE, Sigma, and other security datasets."""

import json
import logging
import re
import requests
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Iterator
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class KnowledgeDocument:
    """Standardized document structure for knowledge corpus."""
    id: str
    title: str
    content: str
    doc_type: str  # attack_technique, cve, sigma_rule, etc.
    source: str
    url: str = ""
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class ATTACKLoader:
    """Loader for MITRE ATT&CK framework data."""
    
    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path("knowledge/corpora/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def load_demo_slice(self) -> List[KnowledgeDocument]:
        """Load a small demo slice of ATT&CK techniques for testing."""
        
        # Demo techniques covering common attack patterns
        demo_techniques = [
            {
                "id": "T1021.004",
                "name": "Remote Services: SSH", 
                "description": "Adversaries may use Valid Accounts to log into remote machines using Secure Shell (SSH). The adversary may then perform actions as the logged-on user.",
                "tactic": "Lateral Movement",
                "platforms": ["Linux", "macOS"],
                "data_sources": ["Authentication Logs", "Network Traffic"],
                "url": "https://attack.mitre.org/techniques/T1021/004/"
            },
            {
                "id": "T1078",
                "name": "Valid Accounts",
                "description": "Adversaries may obtain and abuse credentials of existing accounts as a means of gaining Initial Access, Persistence, Privilege Escalation, or Defense Evasion.",
                "tactic": "Defense Evasion",
                "platforms": ["Linux", "Windows", "macOS", "SaaS", "IaaS", "Network"],
                "data_sources": ["Authentication Logs", "Windows Event Logs"],
                "url": "https://attack.mitre.org/techniques/T1078/"
            },
            {
                "id": "T1003",
                "name": "OS Credential Dumping",
                "description": "Adversaries may attempt to dump credentials to obtain account login and credential material, normally in the form of a hash or a clear text password.",
                "tactic": "Credential Access",
                "platforms": ["Linux", "Windows", "macOS"],
                "data_sources": ["Process Monitoring", "File Monitoring", "API Monitoring"],
                "url": "https://attack.mitre.org/techniques/T1003/"
            },
            {
                "id": "T1047",
                "name": "Windows Management Instrumentation",
                "description": "Adversaries may abuse Windows Management Instrumentation (WMI) to execute malicious commands and payloads.",
                "tactic": "Execution",
                "platforms": ["Windows"],
                "data_sources": ["Authentication Logs", "Network Traffic", "Process Monitoring"],
                "url": "https://attack.mitre.org/techniques/T1047/"
            },
            {
                "id": "T1190",
                "name": "Exploit Public-Facing Application",
                "description": "Adversaries may attempt to take advantage of a weakness in an Internet-facing computer or program using software, data, or commands in order to cause unintended or unanticipated behavior.",
                "tactic": "Initial Access",
                "platforms": ["Linux", "Windows", "macOS", "Network"],
                "data_sources": ["Application Logs", "Network Traffic"],
                "url": "https://attack.mitre.org/techniques/T1190/"
            },
            {
                "id": "T1505.003",
                "name": "Server Software Component: Web Shell",
                "description": "Adversaries may backdoor web servers with web shells to establish persistent access to systems.",
                "tactic": "Persistence",
                "platforms": ["Linux", "Windows", "macOS", "Network"],
                "data_sources": ["File Monitoring", "Network Traffic", "Process Monitoring"],
                "url": "https://attack.mitre.org/techniques/T1505/003/"
            },
            {
                "id": "T1486",
                "name": "Data Encrypted for Impact",
                "description": "Adversaries may encrypt data on target systems or on large numbers of systems in a network to interrupt availability to system and network resources.",
                "tactic": "Impact",
                "platforms": ["Linux", "Windows", "macOS"],
                "data_sources": ["File Monitoring", "Process Monitoring"],
                "url": "https://attack.mitre.org/techniques/T1486/"
            },
            {
                "id": "T1041",
                "name": "Exfiltration Over C2 Channel",
                "description": "Adversaries may steal data by exfiltrating it over an existing command and control channel.",
                "tactic": "Exfiltration",
                "platforms": ["Linux", "Windows", "macOS"],
                "data_sources": ["Network Traffic", "Process Monitoring"],
                "url": "https://attack.mitre.org/techniques/T1041/"
            },
            {
                "id": "T1071.004",
                "name": "Application Layer Protocol: DNS",
                "description": "Adversaries may communicate using the Domain Name System (DNS) application layer protocol to avoid detection/network filtering by blending in with existing traffic.",
                "tactic": "Command and Control",
                "platforms": ["Linux", "Windows", "macOS"],
                "data_sources": ["Network Traffic", "Packet Capture"],
                "url": "https://attack.mitre.org/techniques/T1071/004/"
            },
            {
                "id": "T1195",
                "name": "Supply Chain Compromise",
                "description": "Adversaries may manipulate products or product delivery mechanisms prior to receipt by a final consumer for the purpose of data or system compromise.",
                "tactic": "Initial Access",
                "platforms": ["Linux", "Windows", "macOS"],
                "data_sources": ["File Monitoring", "Web Proxy"],
                "url": "https://attack.mitre.org/techniques/T1195/"
            }
        ]
        
        documents = []
        for technique in demo_techniques:
            # Create main technique document
            content = f"""Technique: {technique['name']}
ID: {technique['id']}
Tactic: {technique['tactic']}
Platforms: {', '.join(technique['platforms'])}

Description:
{technique['description']}

Data Sources:
{', '.join(technique['data_sources'])}
"""
            
            doc = KnowledgeDocument(
                id=technique['id'],
                title=technique['name'],
                content=content,
                doc_type="attack_technique",
                source="mitre_attack_demo",
                url=technique['url'],
                metadata={
                    "tactic": technique['tactic'],
                    "platforms": technique['platforms'],
                    "data_sources": technique['data_sources'],
                    "attack_id": technique['id']
                }
            )
            documents.append(doc)
        
        logger.info(f"Loaded {len(documents)} demo ATT&CK techniques")
        return documents
    
    def load_full_enterprise(
        self,
        *,
        offline_bundle_path: Optional[Path] = None,
        force: bool = False,
    ) -> List[KnowledgeDocument]:
        """Load full ATT&CK Enterprise matrix via STIX/TAXII.

        Args:
            offline_bundle_path: Path to a local STIX bundle JSON for offline mode.
            force: If True, skip incremental diff and treat all docs as new.
        """
        from knowledge.corpora.attack_stix import ATTACKIngestPipeline

        pipeline = ATTACKIngestPipeline(
            cache_dir=self.cache_dir,
            offline_bundle_path=offline_bundle_path,
        )
        docs, stats = pipeline.run(force=force)
        logger.info(
            f"Loaded {stats['techniques_parsed']} ATT&CK techniques via STIX/TAXII "
            f"({stats['docs_to_upsert']} to upsert, {stats['docs_unchanged']} unchanged)"
        )
        return docs

class CVELoader:
    """Loader for CVE/NVD vulnerability data."""
    
    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path("knowledge/corpora/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def load_demo_slice(self) -> List[KnowledgeDocument]:
        """Load a small demo slice of CVE data for testing."""
        
        demo_cves = [
            {
                "id": "CVE-2021-44228",
                "description": "Apache Log4j2 2.0-beta9 through 2.15.0 (excluding security releases 2.12.2, 2.12.3, and 2.3.1) JNDI features used in configuration, log messages, and parameters do not protect against attacker controlled LDAP and other JNDI related endpoints.",
                "cvss_score": 10.0,
                "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
                "cwe": "CWE-502",
                "published": "2021-12-10",
                "affected_products": ["Apache Log4j"],
                "references": [
                    "https://logging.apache.org/log4j/2.x/security.html"
                ]
            },
            {
                "id": "CVE-2021-34527",
                "description": "Windows Print Spooler Remote Code Execution Vulnerability (PrintNightmare)",
                "cvss_score": 8.8,
                "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",
                "cwe": "CWE-269",
                "published": "2021-07-01",
                "affected_products": ["Microsoft Windows"],
                "references": [
                    "https://msrc.microsoft.com/update-guide/vulnerability/CVE-2021-34527"
                ]
            },
            {
                "id": "CVE-2021-40444",
                "description": "Microsoft MSHTML Remote Code Execution Vulnerability",
                "cvss_score": 8.8,
                "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H",
                "cwe": "CWE-416",
                "published": "2021-09-15",
                "affected_products": ["Microsoft Windows"],
                "references": [
                    "https://msrc.microsoft.com/update-guide/vulnerability/CVE-2021-40444"
                ]
            },
            {
                "id": "CVE-2022-22965",
                "description": "Spring Framework Remote Code Execution Vulnerability (Spring4Shell)",
                "cvss_score": 9.8,
                "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                "cwe": "CWE-94",
                "published": "2022-04-01",
                "affected_products": ["Spring Framework"],
                "references": [
                    "https://spring.io/blog/2022/03/31/spring-framework-rce-early-announcement"
                ]
            },
            {
                "id": "CVE-2022-26134",
                "description": "Atlassian Confluence Server and Data Center Remote Code Execution",
                "cvss_score": 9.8,
                "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                "cwe": "CWE-94",
                "published": "2022-06-02",
                "affected_products": ["Atlassian Confluence"],
                "references": [
                    "https://confluence.atlassian.com/doc/confluence-security-advisory-2022-06-02-1130377146.html"
                ]
            }
        ]
        
        documents = []
        for cve in demo_cves:
            content = f"""CVE: {cve['id']}
CVSS Score: {cve['cvss_score']} ({cve['cvss_vector']})
CWE: {cve['cwe']}
Published: {cve['published']}

Description:
{cve['description']}

Affected Products:
{', '.join(cve['affected_products'])}

References:
{chr(10).join('- ' + ref for ref in cve['references'])}
"""
            
            doc = KnowledgeDocument(
                id=cve['id'],
                title=f"{cve['id']} - {cve['description'][:100]}...",
                content=content,
                doc_type="cve",
                source="nvd_demo",
                url=f"https://nvd.nist.gov/vuln/detail/{cve['id']}",
                metadata={
                    "cvss_score": cve['cvss_score'],
                    "cvss_vector": cve['cvss_vector'],
                    "cwe": cve['cwe'],
                    "published": cve['published'],
                    "affected_products": cve['affected_products'],
                    "cve_id": cve['id']
                }
            )
            documents.append(doc)
        
        logger.info(f"Loaded {len(documents)} demo CVEs")
        return documents

class SigmaLoader:
    """Loader for Sigma detection rules."""
    
    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path("knowledge/corpora/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def load_demo_slice(self) -> List[KnowledgeDocument]:
        """Load demo Sigma rules for testing."""
        
        demo_rules = [
            {
                "title": "SSH Brute Force Attack",
                "id": "1126def4-9c66-4de5-9af2-c4716fe83216",
                "description": "Detects SSH brute force attacks by monitoring failed login attempts",
                "author": "CyberSentinel",
                "level": "medium",
                "logsource": {
                    "product": "linux",
                    "service": "sshd"
                },
                "detection": {
                    "selection": {
                        "program": "sshd",
                        "message": ["*Failed password*", "*Invalid user*"]
                    },
                    "timeframe": "10m",
                    "condition": "selection | count() > 5"
                },
                "tags": ["attack.credential_access", "attack.t1110"],
                "references": ["https://attack.mitre.org/techniques/T1110/"]
            },
            {
                "title": "Suspicious Process Execution via SSH",
                "id": "2237abc5-8d77-5ef6-8bg3-d5827gf94327",
                "description": "Detects suspicious process execution after SSH login",
                "author": "CyberSentinel",
                "level": "high",
                "logsource": {
                    "product": "linux",
                    "category": "process_creation"
                },
                "detection": {
                    "selection": {
                        "parent_process": "*sshd*",
                        "process": ["*nc*", "*netcat*", "*python*", "*perl*", "*bash*"]
                    },
                    "condition": "selection"
                },
                "tags": ["attack.execution", "attack.t1059"],
                "references": ["https://attack.mitre.org/techniques/T1059/"]
            },
            {
                "title": "Web Shell Upload Detection",
                "id": "3348bcd6-9e88-6fg7-9ch4-e6938hg05438",
                "description": "Detects potential web shell uploads to web directories",
                "author": "CyberSentinel", 
                "level": "high",
                "logsource": {
                    "category": "file_event"
                },
                "detection": {
                    "selection": {
                        "target_path": ["*/var/www/*", "*/htdocs/*", "*/wwwroot/*"],
                        "file_extension": [".php", ".asp", ".aspx", ".jsp"]
                    },
                    "keywords": ["eval", "exec", "system", "shell_exec", "passthru"],
                    "condition": "selection and keywords"
                },
                "tags": ["attack.persistence", "attack.t1505.003"],
                "references": ["https://attack.mitre.org/techniques/T1505/003/"]
            },
            {
                "title": "DNS Tunneling Detection",
                "id": "4459cde7-0f99-7gh8-0di5-f7049ig16549",
                "description": "Detects potential DNS tunneling based on unusual query patterns",
                "author": "CyberSentinel",
                "level": "medium",
                "logsource": {
                    "category": "dns"
                },
                "detection": {
                    "selection": {
                        "query_length": ">50",
                        "query_type": ["TXT", "CNAME"]
                    },
                    "timeframe": "5m",
                    "condition": "selection | count() > 10"
                },
                "tags": ["attack.exfiltration", "attack.t1071.004"],
                "references": ["https://attack.mitre.org/techniques/T1071/004/"]
            },
            {
                "title": "Credential Dumping with Mimikatz",
                "id": "5560def8-1g00-8hi9-1ej6-g8150jh27650",
                "description": "Detects credential dumping activities using Mimikatz or similar tools",
                "author": "CyberSentinel",
                "level": "critical",
                "logsource": {
                    "product": "windows",
                    "category": "process_creation"
                },
                "detection": {
                    "selection": {
                        "process": "*mimikatz*",
                        "command_line": ["*sekurlsa*", "*lsadump*", "*credentials*"]
                    },
                    "condition": "selection"
                },
                "tags": ["attack.credential_access", "attack.t1003"],
                "references": ["https://attack.mitre.org/techniques/T1003/"]
            }
        ]
        
        documents = []
        for rule in demo_rules:
            # Convert rule to YAML format
            rule_yaml = yaml.dump(rule, default_flow_style=False)
            
            content = f"""Sigma Rule: {rule['title']}
ID: {rule['id']}
Level: {rule['level']}
Author: {rule['author']}

Description:
{rule['description']}

Log Source:
{yaml.dump(rule['logsource'], default_flow_style=False)}

Detection Logic:
{yaml.dump(rule['detection'], default_flow_style=False)}

ATT&CK Tags:
{', '.join(rule['tags'])}

Full Rule (YAML):
```yaml
{rule_yaml}
```
"""
            
            doc = KnowledgeDocument(
                id=rule['id'],
                title=rule['title'],
                content=content,
                doc_type="sigma_rule",
                source="sigma_demo",
                url="",
                metadata={
                    "level": rule['level'],
                    "author": rule['author'],
                    "logsource": rule['logsource'],
                    "tags": rule['tags'],
                    "rule_id": rule['id'],
                    "attack_techniques": [tag.replace('attack.', '') for tag in rule['tags'] if tag.startswith('attack.t')]
                }
            )
            documents.append(doc)
        
        logger.info(f"Loaded {len(documents)} demo Sigma rules")
        return documents

class CISAKEVLoader:
    """Loader for CISA Known Exploited Vulnerabilities (KEV) catalog."""
    
    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path("knowledge/corpora/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def load_demo_slice(self) -> List[KnowledgeDocument]:
        """Load demo CISA KEV entries."""
        
        demo_kevs = [
            {
                "cve": "CVE-2021-44228",
                "vendor": "Apache",
                "product": "Log4j",
                "vulnerability_name": "Apache Log4j2 Remote Code Execution Vulnerability",
                "date_added": "2021-12-10",
                "short_description": "Apache Log4j2 contains a remote code execution vulnerability. An unauthenticated, remote attacker could exploit this vulnerability to take control of an affected system.",
                "required_action": "Apply updates per vendor instructions.",
                "due_date": "2021-12-24",
                "notes": "This vulnerability is being actively exploited and poses significant risk to federal enterprise networks."
            },
            {
                "cve": "CVE-2021-34527",
                "vendor": "Microsoft",
                "product": "Windows Print Spooler",
                "vulnerability_name": "Microsoft Windows Print Spooler Remote Code Execution Vulnerability",
                "date_added": "2021-07-13",
                "short_description": "Microsoft Windows Print Spooler contains an unspecified vulnerability that allows for privilege escalation.",
                "required_action": "Apply updates per vendor instructions.",
                "due_date": "2021-07-27",
                "notes": "Known as PrintNightmare. Actively exploited in the wild."
            },
            {
                "cve": "CVE-2022-22965", 
                "vendor": "VMware",
                "product": "Spring Framework",
                "vulnerability_name": "Spring Framework Remote Code Execution Vulnerability",
                "date_added": "2022-04-04",
                "short_description": "Spring Framework contains a remote code execution vulnerability via data binding.",
                "required_action": "Apply updates per vendor instructions.",
                "due_date": "2022-04-25",
                "notes": "Known as Spring4Shell. Limited exploitation observed."
            }
        ]
        
        documents = []
        for kev in demo_kevs:
            content = f"""CISA KEV Entry: {kev['vulnerability_name']}
CVE: {kev['cve']}
Vendor: {kev['vendor']}
Product: {kev['product']}
Date Added to KEV: {kev['date_added']}
Due Date: {kev['due_date']}

Description:
{kev['short_description']}

Required Action:
{kev['required_action']}

Notes:
{kev.get('notes', 'N/A')}
"""
            
            doc = KnowledgeDocument(
                id=f"KEV-{kev['cve']}",
                title=f"{kev['cve']} - {kev['vulnerability_name']}",
                content=content,
                doc_type="cisa_kev",
                source="cisa_kev_demo",
                url=f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
                metadata={
                    "cve_id": kev['cve'],
                    "vendor": kev['vendor'],
                    "product": kev['product'],
                    "date_added": kev['date_added'],
                    "due_date": kev['due_date'],
                    "actively_exploited": True
                }
            )
            documents.append(doc)
        
        logger.info(f"Loaded {len(documents)} demo CISA KEV entries")
        return documents

class KnowledgeCorpus:
    """Main interface for loading all knowledge sources."""

    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path("knowledge/corpora/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.attack_loader = ATTACKLoader(cache_dir)
        self.cve_loader = CVELoader(cache_dir)
        self.sigma_loader = SigmaLoader(cache_dir)
        self.kev_loader = CISAKEVLoader(cache_dir)

    def load_all(
        self,
        *,
        full_attack: bool = False,
        offline_bundle_path: Optional[Path] = None,
    ) -> List[KnowledgeDocument]:
        """Load all knowledge sources.

        Args:
            full_attack: If True, load full ATT&CK via STIX/TAXII instead of demo slice.
            offline_bundle_path: Path to local STIX bundle for offline full_attack mode.
        """
        logger.info("Loading knowledge corpus (full_attack=%s)…", full_attack)
        all_docs: List[KnowledgeDocument] = []

        if full_attack:
            all_docs.extend(self.attack_loader.load_full_enterprise(
                offline_bundle_path=offline_bundle_path
            ))
        else:
            all_docs.extend(self.attack_loader.load_demo_slice())

        all_docs.extend(self.cve_loader.load_demo_slice())
        all_docs.extend(self.sigma_loader.load_demo_slice())
        all_docs.extend(self.kev_loader.load_demo_slice())

        logger.info(f"Loaded total of {len(all_docs)} knowledge documents")
        doc_types: Dict[str, int] = {}
        for doc in all_docs:
            doc_types[doc.doc_type] = doc_types.get(doc.doc_type, 0) + 1
        logger.info("Document distribution:")
        for doc_type, count in doc_types.items():
            logger.info(f"  {doc_type}: {count}")
        return all_docs

    def load_all_demo_slices(self) -> List[KnowledgeDocument]:
        """Load all demo slices for testing and development."""
        return self.load_all(full_attack=False)

    def load_specific_source(
        self,
        source: str,
        *,
        offline_bundle_path: Optional[Path] = None,
    ) -> List[KnowledgeDocument]:
        """Load documents from a specific source."""

        if source == "attack":
            return self.attack_loader.load_demo_slice()
        elif source == "attack_full":
            return self.attack_loader.load_full_enterprise(
                offline_bundle_path=offline_bundle_path
            )
        elif source == "cve":
            return self.cve_loader.load_demo_slice()
        elif source == "sigma":
            return self.sigma_loader.load_demo_slice()
        elif source == "cisa_kev":
            return self.kev_loader.load_demo_slice()
        else:
            raise ValueError(f"Unknown source: {source}")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge corpus."""

        all_docs = self.load_all_demo_slices()

        stats = {
            "total_documents": len(all_docs),
            "by_type": {},
            "by_source": {},
            "avg_content_length": 0
        }

        total_length = 0
        for doc in all_docs:
            # Count by type
            stats["by_type"][doc.doc_type] = stats["by_type"].get(doc.doc_type, 0) + 1

            # Count by source
            stats["by_source"][doc.source] = stats["by_source"].get(doc.source, 0) + 1

            # Track content length
            total_length += len(doc.content)

        if len(all_docs) > 0:
            stats["avg_content_length"] = total_length / len(all_docs)

        return stats