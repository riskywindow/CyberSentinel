"""Document chunking strategies for different knowledge sources."""

import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import yaml

from knowledge.corpora.loaders import KnowledgeDocument

logger = logging.getLogger(__name__)

@dataclass
class DocumentChunk:
    """A chunk of a knowledge document."""
    id: str  # Unique chunk ID
    doc_id: str  # Parent document ID
    title: str
    content: str
    chunk_type: str  # section, field, full_doc, etc.
    metadata: Dict[str, Any]

class DocumentChunker:
    """Base class for document chunking strategies."""
    
    def chunk(self, document: KnowledgeDocument) -> List[DocumentChunk]:
        """Chunk a document into smaller pieces."""
        raise NotImplementedError

class ATTACKChunker(DocumentChunker):
    """Chunker for ATT&CK technique documents."""
    
    def chunk(self, document: KnowledgeDocument) -> List[DocumentChunk]:
        """Chunk ATT&CK technique into logical sections."""
        
        if document.doc_type != "attack_technique":
            raise ValueError(f"Expected attack_technique, got {document.doc_type}")
        
        chunks = []
        
        # Main technique overview chunk
        technique_id = document.metadata.get("attack_id", document.id)
        tactic = document.metadata.get("tactic", "Unknown")
        platforms = document.metadata.get("platforms", [])
        
        overview_content = f"""ATT&CK Technique: {document.title}
ID: {technique_id}
Tactic: {tactic}
Platforms: {', '.join(platforms)}

{self._extract_description(document.content)}
"""
        
        chunks.append(DocumentChunk(
            id=f"{document.id}_overview",
            doc_id=document.id,
            title=f"{document.title} - Overview",
            content=overview_content,
            chunk_type="technique_overview",
            metadata={
                **document.metadata,
                "chunk_type": "overview",
                "attack_id": technique_id,
                "tactic": tactic
            }
        ))
        
        # Detection chunk (data sources)
        data_sources = document.metadata.get("data_sources", [])
        if data_sources:
            detection_content = f"""Detection for {document.title} ({technique_id}):

Data Sources: {', '.join(data_sources)}

This technique can be detected by monitoring:
{chr(10).join('- ' + ds for ds in data_sources)}

Look for indicators related to {tactic.lower()} activities on {', '.join(platforms)} platforms.
"""
            
            chunks.append(DocumentChunk(
                id=f"{document.id}_detection",
                doc_id=document.id,
                title=f"{document.title} - Detection",
                content=detection_content,
                chunk_type="technique_detection",
                metadata={
                    **document.metadata,
                    "chunk_type": "detection",
                    "data_sources": data_sources
                }
            ))
        
        return chunks
    
    def _extract_description(self, content: str) -> str:
        """Extract description section from ATT&CK content."""
        lines = content.split('\n')
        in_description = False
        description_lines = []
        
        for line in lines:
            if line.startswith("Description:"):
                in_description = True
                continue
            elif in_description and line.strip() and not line.startswith(("Data Sources:", "Platforms:")):
                description_lines.append(line)
            elif in_description and (line.startswith(("Data Sources:", "Platforms:")) or not line.strip()):
                break
        
        return '\n'.join(description_lines).strip()

class CVEChunker(DocumentChunker):
    """Chunker for CVE vulnerability documents."""
    
    def chunk(self, document: KnowledgeDocument) -> List[DocumentChunk]:
        """Chunk CVE into summary and technical details."""
        
        if document.doc_type != "cve":
            raise ValueError(f"Expected cve, got {document.doc_type}")
        
        chunks = []
        cve_id = document.metadata.get("cve_id", document.id)
        cvss_score = document.metadata.get("cvss_score", 0)
        
        # Summary chunk
        summary_content = f"""CVE Summary: {cve_id}
Severity: {self._severity_from_cvss(cvss_score)} (CVSS {cvss_score})

{self._extract_description(document.content)}

Affected Products: {', '.join(document.metadata.get('affected_products', []))}
"""
        
        chunks.append(DocumentChunk(
            id=f"{document.id}_summary",
            doc_id=document.id,
            title=f"{cve_id} - Summary",
            content=summary_content,
            chunk_type="cve_summary",
            metadata={
                **document.metadata,
                "chunk_type": "summary",
                "severity": self._severity_from_cvss(cvss_score)
            }
        ))
        
        # Technical details chunk
        cvss_vector = document.metadata.get("cvss_vector", "")
        cwe = document.metadata.get("cwe", "")
        
        technical_content = f"""Technical Details for {cve_id}:

CVSS Vector: {cvss_vector}
CWE Classification: {cwe}
CVSS Score: {cvss_score}

This vulnerability affects:
{chr(10).join('- ' + product for product in document.metadata.get('affected_products', []))}

The vulnerability allows attackers to {self._impact_from_cvss_vector(cvss_vector)}.
"""
        
        chunks.append(DocumentChunk(
            id=f"{document.id}_technical",
            doc_id=document.id,
            title=f"{cve_id} - Technical Details",
            content=technical_content,
            chunk_type="cve_technical",
            metadata={
                **document.metadata,
                "chunk_type": "technical",
                "cwe": cwe
            }
        ))
        
        return chunks
    
    def _severity_from_cvss(self, score: float) -> str:
        """Convert CVSS score to severity level."""
        if score >= 9.0:
            return "Critical"
        elif score >= 7.0:
            return "High"
        elif score >= 4.0:
            return "Medium"
        else:
            return "Low"
    
    def _extract_description(self, content: str) -> str:
        """Extract description from CVE content."""
        lines = content.split('\n')
        in_description = False
        description_lines = []
        
        for line in lines:
            if line.startswith("Description:"):
                in_description = True
                continue
            elif in_description and line.strip() and not line.startswith(("Affected Products:", "References:")):
                description_lines.append(line)
            elif in_description and (line.startswith(("Affected Products:", "References:")) or not line.strip()):
                break
        
        return '\n'.join(description_lines).strip()
    
    def _impact_from_cvss_vector(self, vector: str) -> str:
        """Extract impact description from CVSS vector."""
        if "C:H" in vector and "I:H" in vector and "A:H" in vector:
            return "gain full control of the system (confidentiality, integrity, and availability impact)"
        elif "C:H" in vector:
            return "access sensitive information (confidentiality impact)"
        elif "I:H" in vector:
            return "modify system data (integrity impact)"
        elif "A:H" in vector:
            return "cause system unavailability (availability impact)"
        else:
            return "potentially compromise the system"

class SigmaChunker(DocumentChunker):
    """Chunker for Sigma detection rules."""
    
    def chunk(self, document: KnowledgeDocument) -> List[DocumentChunk]:
        """Chunk Sigma rule into detection logic and metadata."""
        
        if document.doc_type != "sigma_rule":
            raise ValueError(f"Expected sigma_rule, got {document.doc_type}")
        
        chunks = []
        rule_id = document.metadata.get("rule_id", document.id)
        level = document.metadata.get("level", "medium")
        tags = document.metadata.get("tags", [])
        
        # Rule overview chunk
        overview_content = f"""Sigma Detection Rule: {document.title}
Rule ID: {rule_id}
Severity Level: {level}

{self._extract_description(document.content)}

ATT&CK Techniques: {', '.join(tag.replace('attack.', '').upper() for tag in tags if tag.startswith('attack.t'))}
"""
        
        chunks.append(DocumentChunk(
            id=f"{document.id}_overview",
            doc_id=document.id,
            title=f"{document.title} - Rule Overview",
            content=overview_content,
            chunk_type="sigma_overview",
            metadata={
                **document.metadata,
                "chunk_type": "overview",
                "level": level,
                "attack_techniques": [tag.replace('attack.', '') for tag in tags if tag.startswith('attack.t')]
            }
        ))
        
        # Detection logic chunk
        logsource = document.metadata.get("logsource", {})
        detection_content = f"""Detection Logic for {document.title}:

Log Source:
- Product: {logsource.get('product', 'Unknown')}
- Service: {logsource.get('service', 'Unknown')}
- Category: {logsource.get('category', 'Unknown')}

{self._extract_detection_logic(document.content)}

This rule detects {level} severity events related to {', '.join(tags)}.
"""
        
        chunks.append(DocumentChunk(
            id=f"{document.id}_detection",
            doc_id=document.id,
            title=f"{document.title} - Detection Logic", 
            content=detection_content,
            chunk_type="sigma_detection",
            metadata={
                **document.metadata,
                "chunk_type": "detection_logic",
                "logsource": logsource
            }
        ))
        
        return chunks
    
    def _extract_description(self, content: str) -> str:
        """Extract description from Sigma rule content."""
        lines = content.split('\n')
        in_description = False
        description_lines = []
        
        for line in lines:
            if line.startswith("Description:"):
                in_description = True
                continue
            elif in_description and line.strip() and not line.startswith(("Log Source:", "Detection Logic:")):
                description_lines.append(line)
            elif in_description and (line.startswith(("Log Source:", "Detection Logic:")) or not line.strip()):
                break
        
        return '\n'.join(description_lines).strip()
    
    def _extract_detection_logic(self, content: str) -> str:
        """Extract detection logic from Sigma rule content."""
        lines = content.split('\n')
        in_detection = False
        detection_lines = []
        
        for line in lines:
            if line.startswith("Detection Logic:"):
                in_detection = True
                continue
            elif in_detection and line.strip() and not line.startswith(("ATT&CK Tags:", "Full Rule")):
                detection_lines.append(line)
            elif in_detection and (line.startswith(("ATT&CK Tags:", "Full Rule")) or not line.strip()):
                break
        
        return '\n'.join(detection_lines).strip()

class GenericChunker(DocumentChunker):
    """Generic chunker for other document types."""
    
    def __init__(self, max_chunk_size: int = 1000):
        self.max_chunk_size = max_chunk_size
    
    def chunk(self, document: KnowledgeDocument) -> List[DocumentChunk]:
        """Chunk document by size if no specific chunker available."""
        
        chunks = []
        
        # If document is short, return as single chunk
        if len(document.content) <= self.max_chunk_size:
            chunks.append(DocumentChunk(
                id=f"{document.id}_full",
                doc_id=document.id,
                title=document.title,
                content=document.content,
                chunk_type="full_document",
                metadata={
                    **document.metadata,
                    "chunk_type": "full_document"
                }
            ))
            return chunks
        
        # Split into smaller chunks
        words = document.content.split()
        current_chunk = []
        current_size = 0
        chunk_num = 0
        
        for word in words:
            if current_size + len(word) + 1 > self.max_chunk_size and current_chunk:
                # Create chunk
                chunk_content = ' '.join(current_chunk)
                chunks.append(DocumentChunk(
                    id=f"{document.id}_chunk_{chunk_num}",
                    doc_id=document.id,
                    title=f"{document.title} - Part {chunk_num + 1}",
                    content=chunk_content,
                    chunk_type="text_chunk",
                    metadata={
                        **document.metadata,
                        "chunk_type": "text_chunk",
                        "chunk_number": chunk_num
                    }
                ))
                
                current_chunk = []
                current_size = 0
                chunk_num += 1
            
            current_chunk.append(word)
            current_size += len(word) + 1
        
        # Add final chunk if any content remains
        if current_chunk:
            chunk_content = ' '.join(current_chunk)
            chunks.append(DocumentChunk(
                id=f"{document.id}_chunk_{chunk_num}",
                doc_id=document.id,
                title=f"{document.title} - Part {chunk_num + 1}",
                content=chunk_content,
                chunk_type="text_chunk",
                metadata={
                    **document.metadata,
                    "chunk_type": "text_chunk",
                    "chunk_number": chunk_num
                }
            ))
        
        return chunks

class SmartChunker:
    """Smart chunker that selects appropriate strategy based on document type."""
    
    def __init__(self):
        self.chunkers = {
            "attack_technique": ATTACKChunker(),
            "cve": CVEChunker(),
            "sigma_rule": SigmaChunker(),
        }
        self.generic_chunker = GenericChunker()
    
    def chunk_document(self, document: KnowledgeDocument) -> List[DocumentChunk]:
        """Chunk a document using the appropriate strategy."""
        
        chunker = self.chunkers.get(document.doc_type, self.generic_chunker)
        chunks = chunker.chunk(document)
        
        logger.debug(f"Chunked {document.doc_type} '{document.title}' into {len(chunks)} chunks")
        return chunks
    
    def chunk_documents(self, documents: List[KnowledgeDocument]) -> List[DocumentChunk]:
        """Chunk multiple documents."""
        
        all_chunks = []
        doc_type_counts = {}
        
        for document in documents:
            chunks = self.chunk_document(document)
            all_chunks.extend(chunks)
            
            doc_type = document.doc_type
            doc_type_counts[doc_type] = doc_type_counts.get(doc_type, 0) + len(chunks)
        
        logger.info(f"Chunked {len(documents)} documents into {len(all_chunks)} total chunks")
        for doc_type, count in doc_type_counts.items():
            logger.info(f"  {doc_type}: {count} chunks")
        
        return all_chunks