"""Evaluation Reporter - generates comprehensive reports and visualizations for evaluation results."""

import asyncio
import logging
import json
import jinja2
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
import base64
import io

from eval.framework import EvaluationRun, EvaluationScenario, EvaluationSuite
from eval.metrics import EvaluationScore, MetricResult, BenchmarkResult

logger = logging.getLogger(__name__)

@dataclass
class ReportConfig:
    """Configuration for report generation."""
    title: str
    subtitle: Optional[str] = None
    include_executive_summary: bool = True
    include_detailed_metrics: bool = True
    include_trend_analysis: bool = True
    include_recommendations: bool = True
    include_raw_data: bool = False
    format: str = "html"  # html, json, markdown
    template: str = "standard"

@dataclass
class ReportSection:
    """Individual section in an evaluation report."""
    section_id: str
    title: str
    content: str
    section_type: str  # summary, metrics, charts, recommendations, etc.
    order: int
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class EvaluationReporter:
    """Generates comprehensive evaluation reports and visualizations."""
    
    def __init__(self, templates_dir: Optional[Path] = None, 
                 output_dir: Optional[Path] = None):
        self.templates_dir = templates_dir or Path(__file__).parent / "templates"
        self.output_dir = output_dir or Path(__file__).parent / "reports"
        
        # Create directories
        self.templates_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize Jinja2 environment
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.templates_dir),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )
        
        # Create default templates if they don't exist
        self._create_default_templates()
        
        logger.info(f"Evaluation reporter initialized with output: {self.output_dir}")
    
    def _create_default_templates(self):
        """Create default report templates."""
        
        # HTML report template
        html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ report_title }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
        .header { border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; }
        .title { color: #333; margin-bottom: 10px; }
        .subtitle { color: #666; font-size: 1.2em; }
        .section { margin-bottom: 40px; }
        .section-title { color: #444; border-bottom: 1px solid #ddd; padding-bottom: 10px; margin-bottom: 20px; }
        .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 20px 0; }
        .metric-card { background: #f9f9f9; padding: 20px; border-radius: 8px; border-left: 4px solid #4CAF50; }
        .metric-card.warning { border-left-color: #FF9800; }
        .metric-card.danger { border-left-color: #F44336; }
        .metric-value { font-size: 2em; font-weight: bold; color: #333; }
        .metric-label { color: #666; margin-bottom: 10px; }
        .metric-description { font-size: 0.9em; color: #888; }
        .grade { font-size: 3em; font-weight: bold; padding: 20px; text-align: center; border-radius: 50%; width: 80px; height: 80px; line-height: 80px; margin: 20px auto; }
        .grade-A { background: #4CAF50; color: white; }
        .grade-B { background: #8BC34A; color: white; }
        .grade-C { background: #FF9800; color: white; }
        .grade-D { background: #FF5722; color: white; }
        .grade-F { background: #F44336; color: white; }
        .recommendations { background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .recommendations ul { margin: 0; padding-left: 20px; }
        .summary-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .stat-box { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }
        .stat-number { font-size: 1.8em; font-weight: bold; color: #333; }
        .stat-label { color: #666; font-size: 0.9em; }
        .timeline { margin: 20px 0; }
        .timeline-item { margin: 10px 0; padding: 10px; background: #f5f5f5; border-radius: 4px; }
        .timestamp { color: #666; font-size: 0.9em; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f5f5f5; font-weight: bold; }
        .footer { margin-top: 50px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; text-align: center; }
    </style>
</head>
<body>
    <div class="header">
        <h1 class="title">{{ report_title }}</h1>
        {% if report_subtitle %}<p class="subtitle">{{ report_subtitle }}</p>{% endif %}
        <p><strong>Generated:</strong> {{ generation_time }}</p>
    </div>

    {% for section in sections %}
    <div class="section">
        <h2 class="section-title">{{ section.title }}</h2>
        {{ section.content | safe }}
    </div>
    {% endfor %}

    <div class="footer">
        <p>Generated by CyberSentinel Evaluation System</p>
    </div>
</body>
</html>
        """
        
        html_template_file = self.templates_dir / "standard.html"
        if not html_template_file.exists():
            with open(html_template_file, 'w') as f:
                f.write(html_template)
        
        # Markdown template
        markdown_template = """
# {{ report_title }}

{% if report_subtitle %}{{ report_subtitle }}{% endif %}

**Generated:** {{ generation_time }}

{% for section in sections %}
## {{ section.title }}

{{ section.content }}

{% endfor %}

---
*Generated by CyberSentinel Evaluation System*
        """
        
        markdown_template_file = self.templates_dir / "standard.md"
        if not markdown_template_file.exists():
            with open(markdown_template_file, 'w') as f:
                f.write(markdown_template)
    
    async def generate_evaluation_report(self, evaluation_run: EvaluationRun,
                                       scenario: EvaluationScenario,
                                       evaluation_score: EvaluationScore,
                                       config: ReportConfig) -> str:
        """Generate a comprehensive evaluation report."""
        
        logger.info(f"Generating evaluation report for run {evaluation_run.run_id}")
        
        # Collect report data
        report_data = {
            "report_title": config.title,
            "report_subtitle": config.subtitle,
            "generation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "evaluation_run": evaluation_run,
            "scenario": scenario,
            "evaluation_score": evaluation_score
        }
        
        # Generate report sections
        sections = []
        
        if config.include_executive_summary:
            sections.append(await self._generate_executive_summary(evaluation_run, scenario, evaluation_score))
        
        if config.include_detailed_metrics:
            sections.append(await self._generate_metrics_section(evaluation_score))
        
        if config.include_recommendations:
            sections.append(await self._generate_recommendations_section(evaluation_score))
        
        # Add scenario details
        sections.append(await self._generate_scenario_details(evaluation_run, scenario))
        
        if config.include_raw_data:
            sections.append(await self._generate_raw_data_section(evaluation_run))
        
        report_data["sections"] = sections
        
        # Generate report in requested format
        if config.format == "html":
            report_content = await self._generate_html_report(report_data, config.template)
        elif config.format == "markdown":
            report_content = await self._generate_markdown_report(report_data, config.template)
        elif config.format == "json":
            report_content = await self._generate_json_report(report_data)
        else:
            raise ValueError(f"Unsupported report format: {config.format}")
        
        # Save report to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"evaluation_report_{evaluation_run.run_id[:8]}_{timestamp}.{config.format}"
        report_path = self.output_dir / filename
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"Generated evaluation report: {report_path}")
        return str(report_path)
    
    async def generate_suite_report(self, suite: EvaluationSuite,
                                  evaluation_runs: List[EvaluationRun],
                                  scenarios: Dict[str, EvaluationScenario],
                                  evaluation_scores: List[EvaluationScore],
                                  config: ReportConfig) -> str:
        """Generate a report for an evaluation suite."""
        
        logger.info(f"Generating suite report for {suite.name}")
        
        # Collect suite data
        report_data = {
            "report_title": config.title or f"Evaluation Suite Report: {suite.name}",
            "report_subtitle": config.subtitle or suite.description,
            "generation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "suite": suite,
            "evaluation_runs": evaluation_runs,
            "scenarios": scenarios,
            "evaluation_scores": evaluation_scores
        }
        
        # Generate sections
        sections = []
        
        if config.include_executive_summary:
            sections.append(await self._generate_suite_summary(suite, evaluation_runs, evaluation_scores))
        
        sections.append(await self._generate_suite_metrics_overview(evaluation_scores))
        
        if config.include_trend_analysis and len(evaluation_scores) > 1:
            sections.append(await self._generate_trend_analysis_section(evaluation_scores))
        
        # Individual scenario summaries
        for run, score in zip(evaluation_runs, evaluation_scores):
            scenario = scenarios.get(run.scenario_id)
            if scenario:
                sections.append(await self._generate_scenario_summary(run, scenario, score))
        
        if config.include_recommendations:
            sections.append(await self._generate_suite_recommendations(evaluation_scores))
        
        report_data["sections"] = sections
        
        # Generate report
        if config.format == "html":
            report_content = await self._generate_html_report(report_data, config.template)
        elif config.format == "markdown":
            report_content = await self._generate_markdown_report(report_data, config.template)
        elif config.format == "json":
            report_content = await self._generate_json_report(report_data)
        else:
            raise ValueError(f"Unsupported report format: {config.format}")
        
        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"suite_report_{suite.suite_id}_{timestamp}.{config.format}"
        report_path = self.output_dir / filename
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"Generated suite report: {report_path}")
        return str(report_path)
    
    async def _generate_executive_summary(self, evaluation_run: EvaluationRun,
                                        scenario: EvaluationScenario,
                                        evaluation_score: EvaluationScore) -> ReportSection:
        """Generate executive summary section."""
        
        duration = ""
        if evaluation_run.end_time:
            duration_seconds = (evaluation_run.end_time - evaluation_run.start_time).total_seconds()
            duration = f"{duration_seconds:.0f} seconds"
        
        content = f"""
        <div class="summary-stats">
            <div class="stat-box">
                <div class="stat-number">{evaluation_score.overall_score:.1%}</div>
                <div class="stat-label">Overall Score</div>
            </div>
            <div class="stat-box">
                <div class="grade grade-{evaluation_score.grade}">{evaluation_score.grade}</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{duration}</div>
                <div class="stat-label">Duration</div>
            </div>
        </div>
        
        <h3>Key Findings</h3>
        <ul>
        """
        
        # Add key findings based on scores
        for metric in evaluation_score.metric_results:
            if metric.normalized_score >= 0.9:
                content += f"<li>✅ Excellent {metric.metric_name.lower()}: {metric.normalized_score:.1%}</li>"
            elif metric.normalized_score <= 0.5:
                content += f"<li>❌ Poor {metric.metric_name.lower()}: {metric.normalized_score:.1%}</li>"
        
        content += "</ul>"
        
        if evaluation_score.strengths:
            content += "<h3>Strengths</h3><ul>"
            for strength in evaluation_score.strengths:
                content += f"<li>{strength}</li>"
            content += "</ul>"
        
        if evaluation_score.weaknesses:
            content += "<h3>Areas for Improvement</h3><ul>"
            for weakness in evaluation_score.weaknesses:
                content += f"<li>{weakness}</li>"
            content += "</ul>"
        
        return ReportSection(
            section_id="executive_summary",
            title="Executive Summary",
            content=content,
            section_type="summary",
            order=1
        )
    
    async def _generate_metrics_section(self, evaluation_score: EvaluationScore) -> ReportSection:
        """Generate detailed metrics section."""
        
        content = '<div class="metric-grid">'
        
        for metric in evaluation_score.metric_results:
            # Determine card style based on score
            if metric.normalized_score >= 0.8:
                card_class = "metric-card"
            elif metric.normalized_score >= 0.6:
                card_class = "metric-card warning"
            else:
                card_class = "metric-card danger"
            
            content += f"""
            <div class="{card_class}">
                <div class="metric-label">{metric.metric_name}</div>
                <div class="metric-value">{metric.normalized_score:.1%}</div>
                <div class="metric-description">{metric.description}</div>
                <div style="margin-top: 10px; font-size: 0.9em;">
                    <strong>Value:</strong> {metric.value:.3f} {metric.unit}<br>
                    <strong>Max:</strong> {metric.max_value:.3f} {metric.unit}
                </div>
            </div>
            """
        
        content += "</div>"
        
        # Add detailed breakdown table
        content += """
        <h3>Detailed Metrics</h3>
        <table>
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                    <th>Score</th>
                    <th>Unit</th>
                    <th>Description</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for metric in evaluation_score.metric_results:
            content += f"""
            <tr>
                <td>{metric.metric_name}</td>
                <td>{metric.value:.3f}</td>
                <td>{metric.normalized_score:.1%}</td>
                <td>{metric.unit}</td>
                <td>{metric.description}</td>
            </tr>
            """
        
        content += "</tbody></table>"
        
        return ReportSection(
            section_id="detailed_metrics",
            title="Detailed Metrics",
            content=content,
            section_type="metrics",
            order=2
        )
    
    async def _generate_recommendations_section(self, evaluation_score: EvaluationScore) -> ReportSection:
        """Generate recommendations section."""
        
        content = '<div class="recommendations">'
        content += '<h3>Recommendations for Improvement</h3>'
        
        if evaluation_score.recommendations:
            content += '<ul>'
            for recommendation in evaluation_score.recommendations:
                content += f'<li>{recommendation}</li>'
            content += '</ul>'
        else:
            content += '<p>No specific recommendations at this time. Continue monitoring and testing.</p>'
        
        content += '</div>'
        
        return ReportSection(
            section_id="recommendations",
            title="Recommendations",
            content=content,
            section_type="recommendations",
            order=3
        )
    
    async def _generate_scenario_details(self, evaluation_run: EvaluationRun,
                                       scenario: EvaluationScenario) -> ReportSection:
        """Generate scenario details section."""
        
        content = f"""
        <h3>Scenario Information</h3>
        <table>
            <tr><td><strong>Scenario ID:</strong></td><td>{scenario.id}</td></tr>
            <tr><td><strong>Name:</strong></td><td>{scenario.name}</td></tr>
            <tr><td><strong>Description:</strong></td><td>{scenario.description}</td></tr>
            <tr><td><strong>Duration:</strong></td><td>{scenario.duration_minutes} minutes</td></tr>
            <tr><td><strong>Steps:</strong></td><td>{len(scenario.steps)}</td></tr>
            <tr><td><strong>Hosts:</strong></td><td>{len(scenario.hosts)}</td></tr>
            <tr><td><strong>Tags:</strong></td><td>{', '.join(scenario.tags)}</td></tr>
        </table>
        
        <h3>Execution Timeline</h3>
        <div class="timeline">
        """
        
        start_time = evaluation_run.start_time
        content += f"""
        <div class="timeline-item">
            <strong>Evaluation Started</strong>
            <div class="timestamp">{start_time.strftime('%Y-%m-%d %H:%M:%S')}</div>
        </div>
        """
        
        if evaluation_run.end_time:
            content += f"""
            <div class="timeline-item">
                <strong>Evaluation Completed</strong>
                <div class="timestamp">{evaluation_run.end_time.strftime('%Y-%m-%d %H:%M:%S')}</div>
            </div>
            """
        
        content += "</div>"
        
        # Add step details if available
        if evaluation_run.results and "step_details" in evaluation_run.results:
            content += "<h3>Step Execution Details</h3><table>"
            content += "<thead><tr><th>Step</th><th>Status</th><th>Technique</th><th>Artifacts</th></tr></thead><tbody>"
            
            for step in evaluation_run.results["step_details"]:
                status = "✅ Success" if step.get("success") else "❌ Failed"
                content += f"""
                <tr>
                    <td>{step.get('name', 'Unknown')}</td>
                    <td>{status}</td>
                    <td>{step.get('technique_id', 'N/A')}</td>
                    <td>{step.get('artifacts_generated', 0)}</td>
                </tr>
                """
            
            content += "</tbody></table>"
        
        return ReportSection(
            section_id="scenario_details",
            title="Scenario Details",
            content=content,
            section_type="details",
            order=4
        )
    
    async def _generate_raw_data_section(self, evaluation_run: EvaluationRun) -> ReportSection:
        """Generate raw data section."""
        
        content = "<h3>Raw Evaluation Data</h3>"
        content += "<pre style='background: #f5f5f5; padding: 20px; border-radius: 8px; overflow: auto;'>"
        content += json.dumps({
            "run_id": evaluation_run.run_id,
            "scenario_id": evaluation_run.scenario_id,
            "start_time": evaluation_run.start_time.isoformat(),
            "end_time": evaluation_run.end_time.isoformat() if evaluation_run.end_time else None,
            "status": evaluation_run.status.value,
            "configuration": evaluation_run.configuration,
            "results": evaluation_run.results,
            "metrics": evaluation_run.metrics
        }, indent=2)
        content += "</pre>"
        
        return ReportSection(
            section_id="raw_data",
            title="Raw Data",
            content=content,
            section_type="data",
            order=10
        )
    
    async def _generate_suite_summary(self, suite: EvaluationSuite,
                                    evaluation_runs: List[EvaluationRun],
                                    evaluation_scores: List[EvaluationScore]) -> ReportSection:
        """Generate suite summary section."""
        
        # Calculate suite statistics
        overall_scores = [score.overall_score for score in evaluation_scores]
        avg_score = sum(overall_scores) / len(overall_scores) if overall_scores else 0
        
        successful_runs = len([run for run in evaluation_runs if run.status.value == "completed"])
        
        content = f"""
        <div class="summary-stats">
            <div class="stat-box">
                <div class="stat-number">{len(evaluation_runs)}</div>
                <div class="stat-label">Total Scenarios</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{successful_runs}</div>
                <div class="stat-label">Successful Runs</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{avg_score:.1%}</div>
                <div class="stat-label">Average Score</div>
            </div>
        </div>
        
        <h3>Suite Information</h3>
        <table>
            <tr><td><strong>Suite ID:</strong></td><td>{suite.suite_id}</td></tr>
            <tr><td><strong>Name:</strong></td><td>{suite.name}</td></tr>
            <tr><td><strong>Description:</strong></td><td>{suite.description}</td></tr>
            <tr><td><strong>Parallel Execution:</strong></td><td>{"Yes" if suite.parallel_execution else "No"}</td></tr>
            <tr><td><strong>Timeout:</strong></td><td>{suite.timeout_minutes} minutes</td></tr>
        </table>
        """
        
        return ReportSection(
            section_id="suite_summary",
            title="Suite Summary",
            content=content,
            section_type="summary",
            order=1
        )
    
    async def _generate_suite_metrics_overview(self, evaluation_scores: List[EvaluationScore]) -> ReportSection:
        """Generate suite metrics overview."""
        
        if not evaluation_scores:
            return ReportSection("metrics_overview", "Metrics Overview", "No evaluation scores available", "metrics", 2)
        
        # Calculate average scores by category
        category_averages = {}
        for score in evaluation_scores:
            for category, value in score.category_scores.items():
                if category not in category_averages:
                    category_averages[category] = []
                category_averages[category].append(value)
        
        content = '<div class="metric-grid">'
        
        for category, values in category_averages.items():
            avg_value = sum(values) / len(values)
            
            card_class = "metric-card"
            if avg_value >= 0.8:
                card_class = "metric-card"
            elif avg_value >= 0.6:
                card_class = "metric-card warning"
            else:
                card_class = "metric-card danger"
            
            content += f"""
            <div class="{card_class}">
                <div class="metric-label">{category.replace('_', ' ').title()}</div>
                <div class="metric-value">{avg_value:.1%}</div>
                <div class="metric-description">Average across {len(values)} scenarios</div>
            </div>
            """
        
        content += "</div>"
        
        return ReportSection(
            section_id="metrics_overview",
            title="Metrics Overview",
            content=content,
            section_type="metrics",
            order=2
        )
    
    async def _generate_trend_analysis_section(self, evaluation_scores: List[EvaluationScore]) -> ReportSection:
        """Generate trend analysis section."""
        
        content = "<h3>Performance Trends</h3>"
        content += "<p>Analysis of performance trends across multiple evaluation runs.</p>"
        
        # Simple trend analysis
        if len(evaluation_scores) >= 2:
            first_score = evaluation_scores[0].overall_score
            last_score = evaluation_scores[-1].overall_score
            
            if last_score > first_score:
                trend = "📈 Improving"
                trend_class = "metric-card"
            elif last_score < first_score:
                trend = "📉 Declining"
                trend_class = "metric-card danger"
            else:
                trend = "➡️ Stable"
                trend_class = "metric-card warning"
            
            improvement = last_score - first_score
            
            content += f"""
            <div class="{trend_class}" style="margin: 20px 0;">
                <div class="metric-label">Overall Trend</div>
                <div class="metric-value">{trend}</div>
                <div class="metric-description">
                    Change: {improvement:+.1%} from first to last evaluation
                </div>
            </div>
            """
        
        return ReportSection(
            section_id="trend_analysis",
            title="Trend Analysis",
            content=content,
            section_type="analysis",
            order=3
        )
    
    async def _generate_scenario_summary(self, evaluation_run: EvaluationRun,
                                       scenario: EvaluationScenario,
                                       evaluation_score: EvaluationScore) -> ReportSection:
        """Generate individual scenario summary."""
        
        content = f"""
        <div style="border: 1px solid #ddd; padding: 20px; margin: 10px 0; border-radius: 8px;">
            <h4>{scenario.name}</h4>
            <p>{scenario.description}</p>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin: 15px 0;">
                <div style="text-align: center;">
                    <div style="font-size: 1.5em; font-weight: bold;">{evaluation_score.overall_score:.1%}</div>
                    <div style="color: #666;">Overall Score</div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 1.5em; font-weight: bold;">{evaluation_score.grade}</div>
                    <div style="color: #666;">Grade</div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 1.5em; font-weight: bold;">{evaluation_run.status.value.title()}</div>
                    <div style="color: #666;">Status</div>
                </div>
            </div>
        </div>
        """
        
        return ReportSection(
            section_id=f"scenario_{scenario.id}",
            title=f"Scenario: {scenario.name}",
            content=content,
            section_type="scenario",
            order=5
        )
    
    async def _generate_suite_recommendations(self, evaluation_scores: List[EvaluationScore]) -> ReportSection:
        """Generate suite-wide recommendations."""
        
        # Collect all recommendations
        all_recommendations = []
        for score in evaluation_scores:
            all_recommendations.extend(score.recommendations)
        
        # Count frequency of recommendations
        rec_counts = {}
        for rec in all_recommendations:
            rec_counts[rec] = rec_counts.get(rec, 0) + 1
        
        # Sort by frequency
        sorted_recs = sorted(rec_counts.items(), key=lambda x: x[1], reverse=True)
        
        content = '<div class="recommendations">'
        content += '<h3>Top Recommendations</h3>'
        
        if sorted_recs:
            content += '<ul>'
            for rec, count in sorted_recs[:10]:  # Top 10
                content += f'<li>{rec} <em>(mentioned {count} times)</em></li>'
            content += '</ul>'
        else:
            content += '<p>No specific recommendations identified.</p>'
        
        content += '</div>'
        
        return ReportSection(
            section_id="suite_recommendations",
            title="Suite Recommendations",
            content=content,
            section_type="recommendations",
            order=6
        )
    
    async def _generate_html_report(self, report_data: Dict[str, Any], template_name: str) -> str:
        """Generate HTML report using Jinja2 template."""
        
        try:
            template = self.jinja_env.get_template(f"{template_name}.html")
            return template.render(**report_data)
        except jinja2.TemplateNotFound:
            # Fall back to basic template
            return await self._generate_basic_html_report(report_data)
    
    async def _generate_basic_html_report(self, report_data: Dict[str, Any]) -> str:
        """Generate basic HTML report without template."""
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{report_data['report_title']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .section {{ margin-bottom: 30px; }}
                h1, h2 {{ color: #333; }}
            </style>
        </head>
        <body>
            <h1>{report_data['report_title']}</h1>
            <p>Generated: {report_data['generation_time']}</p>
        """
        
        for section in report_data['sections']:
            html += f"<div class='section'><h2>{section.title}</h2>{section.content}</div>"
        
        html += "</body></html>"
        return html
    
    async def _generate_markdown_report(self, report_data: Dict[str, Any], template_name: str) -> str:
        """Generate Markdown report."""
        
        try:
            template = self.jinja_env.get_template(f"{template_name}.md")
            return template.render(**report_data)
        except jinja2.TemplateNotFound:
            return await self._generate_basic_markdown_report(report_data)
    
    async def _generate_basic_markdown_report(self, report_data: Dict[str, Any]) -> str:
        """Generate basic Markdown report."""
        
        md = f"# {report_data['report_title']}\n\n"
        md += f"Generated: {report_data['generation_time']}\n\n"
        
        for section in report_data['sections']:
            md += f"## {section.title}\n\n"
            # Convert HTML to plain text for markdown
            import re
            content = re.sub('<[^<]+?>', '', section.content)
            md += f"{content}\n\n"
        
        return md
    
    async def _generate_json_report(self, report_data: Dict[str, Any]) -> str:
        """Generate JSON report."""
        
        # Convert complex objects to serializable format
        serializable_data = {}
        
        for key, value in report_data.items():
            if key in ['evaluation_run', 'scenario', 'evaluation_score']:
                if hasattr(value, '__dict__'):
                    serializable_data[key] = asdict(value) if hasattr(value, '__dataclass_fields__') else value.__dict__
                else:
                    serializable_data[key] = str(value)
            else:
                serializable_data[key] = value
        
        return json.dumps(serializable_data, indent=2, default=str)
    
    def list_reports(self) -> List[Dict[str, Any]]:
        """List available reports."""
        
        reports = []
        
        for report_file in self.output_dir.glob("*.html"):
            reports.append({
                "filename": report_file.name,
                "path": str(report_file),
                "size_kb": report_file.stat().st_size / 1024,
                "created": datetime.fromtimestamp(report_file.stat().st_ctime),
                "format": "html"
            })
        
        for report_file in self.output_dir.glob("*.json"):
            reports.append({
                "filename": report_file.name,
                "path": str(report_file),
                "size_kb": report_file.stat().st_size / 1024,
                "created": datetime.fromtimestamp(report_file.stat().st_ctime),
                "format": "json"
            })
        
        # Sort by creation time (newest first)
        reports.sort(key=lambda x: x["created"], reverse=True)
        
        return reports