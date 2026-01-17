export default function PlatformGuidePage() {
  return (
    <div className="platform-guide-container">
      <style>{`
        .platform-guide-container {
          background: #0d1117;
          color: #c9d1d9;
          line-height: 1.6;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif;
          margin: -1.5rem;
          min-height: 100vh;
        }

        .platform-guide-container * {
          margin: 0;
          padding: 0;
          box-sizing: border-box;
        }

        .pg-header {
          background: #1c2128;
          border-bottom: 1px solid #30363d;
          padding: 1.5rem 2rem;
          position: sticky;
          top: 0;
          z-index: 100;
          box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }

        .pg-header h1 {
          font-size: 1.75rem;
          font-weight: 600;
          color: #58a6ff;
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }

        .pg-header h1::before {
          content: "⚡";
          font-size: 2rem;
        }

        .pg-header .subtitle {
          color: #8b949e;
          font-size: 0.9rem;
          margin-top: 0.25rem;
        }

        .pg-container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 2rem;
        }

        .pg-nav {
          background: #161b22;
          border: 1px solid #30363d;
          border-radius: 8px;
          padding: 1.5rem;
          margin-bottom: 2rem;
        }

        .pg-nav h2 {
          font-size: 1.25rem;
          margin-bottom: 1rem;
          color: #3fb950;
        }

        .pg-nav-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 0.75rem;
        }

        .pg-nav-link {
          display: block;
          padding: 0.75rem 1rem;
          background: #0d1117;
          border: 1px solid #30363d;
          border-radius: 6px;
          color: #58a6ff;
          text-decoration: none;
          transition: all 0.2s;
          cursor: pointer;
        }

        .pg-nav-link:hover {
          background: #1c2128;
          border-color: #58a6ff;
          transform: translateX(4px);
        }

        .pg-section {
          background: #161b22;
          border: 1px solid #30363d;
          border-radius: 8px;
          padding: 2rem;
          margin-bottom: 2rem;
        }

        .pg-intro-section {
          background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
          border: 1px solid #30363d;
          border-radius: 8px;
          padding: 2rem;
          margin-bottom: 2rem;
        }

        .pg-section h2 {
          font-size: 1.75rem;
          color: #3fb950;
          margin-bottom: 1.5rem;
          border-bottom: 2px solid #30363d;
          padding-bottom: 0.5rem;
        }

        .pg-intro-section h2 {
          font-size: 1.75rem;
          color: #3fb950;
          margin-bottom: 1.5rem;
          border-bottom: 2px solid #30363d;
          padding-bottom: 0.5rem;
        }

        .pg-section h3 {
          font-size: 1.35rem;
          color: #58a6ff;
          margin: 1.5rem 0 1rem 0;
        }

        .pg-section h4 {
          font-size: 1.1rem;
          color: #bc8cff;
          margin: 1rem 0 0.75rem 0;
        }

        .pg-section h5 {
          font-size: 1rem;
          margin: 1rem 0 0.5rem 0;
        }

        .pg-section p {
          margin-bottom: 1rem;
          color: #c9d1d9;
        }

        .pg-intro-section p {
          margin-bottom: 1rem;
          color: #c9d1d9;
        }

        .pg-section ul {
          margin: 0.5rem 0 1rem 1.5rem;
        }

        .pg-intro-section ul {
          margin: 0.5rem 0 1rem 1.5rem;
        }

        .pg-section li {
          margin-bottom: 0.5rem;
          line-height: 1.6;
        }

        .pg-intro-section li {
          margin-bottom: 0.5rem;
          line-height: 1.6;
        }

        .pg-highlight-box {
          background: rgba(88, 166, 255, 0.1);
          border-left: 3px solid #58a6ff;
          padding: 1rem;
          margin: 1rem 0;
          border-radius: 4px;
        }

        .pg-highlight-box p {
          margin: 0;
        }

        .pg-table {
          width: 100%;
          border-collapse: collapse;
          margin: 1rem 0;
          background: #0d1117;
          border-radius: 6px;
          overflow: hidden;
        }

        .pg-table thead {
          background: #1c2128;
        }

        .pg-table th {
          padding: 1rem;
          text-align: left;
          font-weight: 600;
          color: #58a6ff;
          border-bottom: 2px solid #30363d;
        }

        .pg-table td {
          padding: 1rem;
          border-bottom: 1px solid #30363d;
        }

        .pg-table tbody tr:last-child td {
          border-bottom: none;
        }

        .pg-table tbody tr:hover {
          background: rgba(88, 166, 255, 0.05);
        }

        .pg-raci-a {
          display: inline-block;
          background: #3fb950;
          color: #0d1117;
          padding: 0.25rem 0.75rem;
          border-radius: 4px;
          font-weight: 600;
          font-size: 0.85rem;
        }

        .pg-raci-r {
          display: inline-block;
          background: #58a6ff;
          color: #0d1117;
          padding: 0.25rem 0.75rem;
          border-radius: 4px;
          font-weight: 600;
          font-size: 0.85rem;
        }

        .pg-status-badge {
          display: inline-block;
          padding: 0.25rem 0.75rem;
          border-radius: 4px;
          font-size: 0.85rem;
          font-weight: 600;
        }

        .pg-status-operational {
          background: #3fb950;
          color: #0d1117;
        }

        .pg-status-demo {
          background: #ffc107;
          color: #0d1117;
        }

        .pg-checkmark {
          color: #3fb950;
          font-weight: bold;
          margin-right: 0.5rem;
        }

        .text-gray-300 {
          color: #c9d1d9;
        }

        @media (max-width: 768px) {
          .pg-container {
            padding: 1rem;
          }

          .pg-section {
            padding: 1rem;
          }

          .pg-nav-grid {
            grid-template-columns: 1fr;
          }

          .pg-table {
            font-size: 0.85rem;
          }

          .pg-table th, .pg-table td {
            padding: 0.5rem;
          }
        }
      `}</style>

      <div className="pg-header">
        <h1>AutonomOS Platform Guide</h1>
        <div className="subtitle">Multi-Tenant AI Orchestration Platform</div>
      </div>

      <div className="pg-container">
        {/* Navigation */}
        <div className="pg-nav">
          <h2>Quick Navigation</h2>
          <div className="pg-nav-grid">
            <a href="#what-is" className="pg-nav-link">What is AutonomOS?</a>
            <a href="#accountability" className="pg-nav-link">Component Ownership</a>
            <a href="#components" className="pg-nav-link">Platform Components</a>
            <a href="#connectors" className="pg-nav-link">Production Connectors</a>
            <a href="#roadmap" className="pg-nav-link">Platform Roadmap</a>
          </div>
        </div>

        {/* What is AutonomOS */}
        <section id="what-is" className="pg-intro-section">
          <h2>What is AutonomOS?</h2>
          
          <p className="text-gray-300">
            AutonomOS is an AI-native, <strong style={{color: '#fff'}}>enterprise-grade</strong> platform that turns your scattered company data into action.
          </p>
          
          <p className="text-gray-300">
            It autonomously connects to all your apps, databases, and files, learning how they fit together to create a single, unified enterprise <strong style={{color: '#fff'}}>ontology</strong>. This allows our specialized AI agents to reason, act, and get work done. Humans use that same ontology to get real-time, accurate, contextual information.
          </p>

          <div className="pg-highlight-box">
            <p><strong>Our Core Tenet:</strong> We abstract complexity away. We'll get you context regardless of how disparate, numerous, and complex your data sources are.</p>
          </div>

          <div className="pg-highlight-box">
            <p><strong>The Problem:</strong> Most companies are data-rich but action-poor. They can't bridge the Insight-to-Action Gap between their data and their business goals, leading to inefficiency and inaction.</p>
          </div>

          <div className="pg-highlight-box">
            <p><strong>What Makes Us Different:</strong> We create autonomous actions, not just insights. We abstract the complexity of disparate data stacks so you don't have to worry about integration headaches. AutonomOS is an end-to-end platform that autonomously connects, understands, and acts on your data—empowering pre-built AI agents to execute complex workflows while you remain in control with Human-in-the-Loop (HITL) guardrails.</p>
          </div>

          <p className="text-gray-300">
            We deliver a complete, secure, and scalable solution combining technology with domain expertise to ensure you get <strong style={{color: '#fff'}}>results</strong>.
          </p>

          <h3 style={{marginTop: '2rem', marginBottom: '1rem', color: '#58a6ff'}}>Current Status</h3>
          <div className="pg-highlight-box">
            <strong>Phase 4 Complete</strong> - Production Ready<br/>
            <strong>Platform State:</strong> All four phases operational with live telemetry monitoring
          </div>

          <h4 style={{color: '#bc8cff'}}>Platform Modules</h4>
          <p style={{marginBottom: '1rem', color: '#8b949e'}}>The platform is built from six core modules, each responsible for specific capabilities.</p>
          
          <h5 style={{color: '#3fb950', marginTop: '1rem', marginBottom: '0.5rem'}}>Operational Modules</h5>
          <ul>
            <li><strong>AOD (Autonomous Object Discovery):</strong> Asset cataloging, Shadow IT detection, HITL triage - <span style={{color: '#3fb950'}}>Production Ready</span></li>
            <li><strong>AAM (Adaptive API Mesh):</strong> Data connectivity, 4 production connectors, drift detection - <span style={{color: '#3fb950'}}>Production Ready</span></li>
            <li><strong>DCL (Data Connection Layer):</strong> AI entity mapping, knowledge graphs, agent context - <span style={{color: '#3fb950'}}>Production Ready</span></li>
          </ul>
          
          <h5 style={{color: '#ffc107', marginTop: '1rem', marginBottom: '0.5rem'}}>Work in Progress Modules</h5>
          <ul>
            <li><strong>AOA (Agentic Orchestration Architecture):</strong> High-level agent orchestration and workflow automation - <span style={{color: '#ffc107'}}>In Development</span></li>
            <li><strong><a href="https://autonomos.cloud" style={{color: '#58a6ff', textDecoration: 'none'}}>RevOps Agent</a>:</strong> Revenue operations automation and CRM intelligence - <span style={{color: '#ffc107'}}>In Development</span></li>
            <li><strong><a href="https://autonomos.technology" style={{color: '#58a6ff', textDecoration: 'none'}}>FinOps Agent</a>:</strong> Financial operations and cloud cost optimization - <span style={{color: '#ffc107'}}>In Development</span></li>
            <li><strong>NLP Intent / Control Center:</strong> Natural language interface for platform control - <span style={{color: '#ffc107'}}>In Development</span></li>
          </ul>
        </section>

        {/* Accountability Matrix */}
        <section id="accountability" className="pg-section">
          <h2>Component Accountability Matrix</h2>
          
          <div className="pg-highlight-box">
            <strong>Purpose:</strong> Clear ownership boundaries ensure architectural integrity and prevent responsibility drift.
          </div>

          <h3>Who Owns What</h3>
          
          <table className="pg-table">
            <thead>
              <tr>
                <th style={{width: '50%'}}>Capability</th>
                <th style={{width: '15%'}}>Owner</th>
                <th style={{width: '35%'}}>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={3} style={{background: '#1c2128', fontWeight: 'bold', color: '#3fb950'}}>Data Discovery & Collection</td>
              </tr>
              <tr>
                <td>Finding your data sources</td>
                <td><span className="pg-raci-a">AOD</span></td>
                <td>Automatically discovers where your data lives across your company</td>
              </tr>
              <tr>
                <td>Connecting to your apps</td>
                <td><span className="pg-raci-a">AAM</span></td>
                <td>Handles logins, passwords, and security for each data source</td>
              </tr>
              <tr>
                <td>Pulling data from sources</td>
                <td><span className="pg-raci-a">AAM</span></td>
                <td>Fetches your actual data and keeps it synchronized</td>
              </tr>
              <tr>
                <td colSpan={3} style={{background: '#1c2128', fontWeight: 'bold', color: '#58a6ff'}}>Intelligence & Understanding</td>
              </tr>
              <tr>
                <td>Understanding your data structure</td>
                <td><span className="pg-raci-a">DCL</span></td>
                <td>AI figures out what your data means and how it relates</td>
              </tr>
              <tr>
                <td>Detecting when data changes</td>
                <td><span className="pg-raci-a">AAM</span></td>
                <td>Notices when your source systems add or change fields</td>
              </tr>
              <tr>
                <td>Fixing broken connections automatically</td>
                <td><span className="pg-raci-a">DCL</span></td>
                <td>AI automatically repairs mappings when sources change</td>
              </tr>
              <tr>
                <td colSpan={3} style={{background: '#1c2128', fontWeight: 'bold', color: '#bc8cff'}}>Action & Execution</td>
              </tr>
              <tr>
                <td>Running AI agents with your data</td>
                <td><span className="pg-raci-r">AOA</span></td>
                <td>Gives agents the right data context to take actions</td>
              </tr>
              <tr>
                <td>Orchestrating workflows</td>
                <td><span className="pg-raci-a">AOA</span></td>
                <td>Coordinates complex business processes across systems</td>
              </tr>
              <tr>
                <td>Monitoring what's happening</td>
                <td><span className="pg-raci-r">Platform</span></td>
                <td>Shows you data flowing through the system in real-time</td>
              </tr>
            </tbody>
          </table>

          <h3>Layer Hierarchy</h3>
          <div className="pg-highlight-box">
            <p style={{marginBottom: '0.75rem'}}><strong>Data flows through the system in this order:</strong></p>
            <p style={{fontFamily: 'monospace', fontSize: '0.95rem'}}>
              <strong style={{color: '#3fb950'}}>AOD (Discovery Layer)</strong> - Finds data sources and catalogs assets<br/>
              ↓<br/>
              <strong style={{color: '#3fb950'}}>AAM (Transport Layer)</strong> - Connects, fetches, and normalizes data<br/>
              ↓<br/>
              <strong style={{color: '#3fb950'}}>DCL (Intelligence Layer)</strong> - Makes sense of data and powers AI agents<br/>
              ↓<br/>
              <strong style={{color: '#ffc107'}}>AOA (Orchestration Layer)</strong> - Coordinates multi-step workflows<br/>
              ↓<br/>
              <strong style={{color: '#ffc107'}}>Agents (Action Layer)</strong> - Execute business workflows
            </p>
          </div>
        </section>

        {/* Platform Components */}
        <section id="components" className="pg-section">
          <h2>Platform Components</h2>
          <p style={{marginBottom: '1.5rem', color: '#8b949e'}}>
            Here's what each part of the platform does, explained in simple terms.
          </p>

          <h3>AOD (Autonomous Object Discovery)</h3>
          <p style={{marginBottom: '1rem', color: '#8b949e'}}>
            The "scout" that automatically finds all the places your company stores data—databases, spreadsheets, cloud apps, file servers—even ones IT doesn't know about (Shadow IT).
          </p>
          <ul>
            <li><strong>Asset Discovery:</strong> Automatically scans your network and cloud to find data sources</li>
            <li><strong>Shadow IT Detection:</strong> Machine learning identifies risky unauthorized data sources.</li>
            <li><strong>NLP Query Interface:</strong> <span className="pg-status-badge pg-status-demo">Demo</span> Ask questions in plain English to find data sources (example: "show me all production databases")</li>
            <li><strong>Human Review Workflow:</strong> Security analysts can approve, quarantine, or investigate discovered assets</li>
            <li><strong>Auto-Connect to AAM:</strong> Approved sources automatically connect to the data mesh</li>
          </ul>

          <h3>AAM (Adaptive API Mesh)</h3>
          <p style={{marginBottom: '1rem', color: '#8b949e'}}>
            The "plumbing" that connects to all your data sources, pulls data, and keeps everything synchronized - even when source systems change.
          </p>
          <ul>
            <li><strong>4 Production Connectors:</strong> Salesforce (CRM), MongoDB (database), FileSource (CSV/Excel), Supabase (PostgreSQL)</li>
            <li><strong>Unified Data Format:</strong> Converts different data formats into a standard structure your company can use</li>
            <li><strong>Change Detection:</strong> Automatically notices when a source system adds or removes fields</li>
            <li><strong>Self-Healing:</strong> AI automatically fixes broken connections when source systems change their structure</li>
          </ul>

          <h3>DCL (Data Connection Layer)</h3>
          <p style={{marginBottom: '1rem', color: '#8b949e'}}>
            The "brain" that builds your enterprise ontology—a unified understanding of how all your data connects and relates across every system.
          </p>
          
          <div className="pg-highlight-box" style={{marginBottom: '1rem'}}>
            <p><strong>Why Ontology Matters:</strong> Without an ontology, each system speaks its own language. "customer_id" in Salesforce, "cust_id" in your database, and "client_num" in your spreadsheets all mean the same thing—but your tools don't know that. DCL creates a single source of truth that both AI agents and humans can use to get accurate, contextual answers across all your data sources.</p>
          </div>
          
          <ul>
            <li><strong>Enterprise Ontology:</strong> Single unified model of your business showing how entities relate (customers → orders → products → suppliers)</li>
            <li><strong>AI-Powered Mapping:</strong> LLM automatically understands how fields from different sources match up, eliminating manual data engineering</li>
            <li><strong>Knowledge Graph Generation:</strong> Visual representation of your ontology that updates in real-time as data changes</li>
            <li><strong>Agent Context Provider:</strong> Gives AI agents the full context they need to take accurate, informed actions</li>
            <li><strong>Multi-Company Support:</strong> Keeps different companies' data completely separate and secure with tenant isolation</li>
          </ul>

          <h3>Live Flow Monitoring</h3>
          <p style={{marginBottom: '1rem', color: '#8b949e'}}>
            Real-time dashboard showing data flowing through the system: Discovery → Connection → Intelligence → AI Agents
          </p>
          <ul>
            <li><strong>Real-Time Visualization:</strong> See data move through the pipeline as it happens</li>
            <li><strong>Event Tracking:</strong> Monitor every step from discovery to AI agent execution</li>
            <li><strong>Instant Updates:</strong> WebSocket streaming with less than 1 second latency</li>
          </ul>
        </section>

        {/* Production Connectors */}
        <section id="connectors" className="pg-section">
          <h2>Production Connectors (4 Operational)</h2>
          <p style={{marginBottom: '1.5rem', color: '#8b949e'}}>
            These are the data sources we can connect to right now. Each connector handles authentication, data fetching, and automatic updates.
          </p>

          <table className="pg-table">
            <thead>
              <tr>
                <th>Connector</th>
                <th>Type</th>
                <th>Status</th>
                <th>What It Does</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Salesforce</strong></td>
                <td>CRM Platform</td>
                <td><span className="pg-status-badge pg-status-operational">Live</span></td>
                <td>Connects to your Salesforce accounts, contacts, and opportunities</td>
              </tr>
              <tr>
                <td><strong>MongoDB</strong></td>
                <td>NoSQL Database</td>
                <td><span className="pg-status-badge pg-status-operational">Live</span></td>
                <td>Pulls data from MongoDB document databases</td>
              </tr>
              <tr>
                <td><strong>FileSource</strong></td>
                <td>Spreadsheets</td>
                <td><span className="pg-status-badge pg-status-operational">Live</span></td>
                <td>Reads CSV and Excel files your team uses</td>
              </tr>
              <tr>
                <td><strong>Supabase</strong></td>
                <td>Cloud Database</td>
                <td><span className="pg-status-badge pg-status-operational">Live</span></td>
                <td>Connects to Supabase PostgreSQL databases with real-time sync</td>
              </tr>
            </tbody>
          </table>

          <h3>What Each Connector Can Do</h3>
          <ul>
            <li><span className="pg-checkmark">✓</span> Secure authentication (OAuth 2.0 where available)</li>
            <li><span className="pg-checkmark">✓</span> Automatic discovery of data structure</li>
            <li><span className="pg-checkmark">✓</span> Converts data to unified format</li>
            <li><span className="pg-checkmark">✓</span> Detects and auto-repairs when source changes</li>
            <li><span className="pg-checkmark">✓</span> Production credentials stored securely</li>
          </ul>
        </section>

        {/* Roadmap */}
        <section id="roadmap" className="pg-section">
          <h2>Platform Roadmap</h2>
          <p style={{marginBottom: '1.5rem', color: '#8b949e'}}>
            Here's what's built, what's in progress, and what's next for each module of the platform.
          </p>

          <h3>AOD (Autonomous Object Discovery)</h3>
          <p style={{marginBottom: '0.5rem'}}><strong>Status:</strong> <span style={{color: '#3fb950'}}>MVP Complete - Production Ready</span></p>
          <p style={{marginBottom: '1rem', color: '#8b949e', fontStyle: 'italic'}}>
            External microservice managing 415 assets with 62 currently in triage (F1 score 85-92%)
          </p>
          
          <h4 style={{color: '#3fb950'}}>MVP Complete</h4>
          <ul>
            <li>Hybrid discovery engine (Rules-only, ML-only, Hybrid modes)</li>
            <li>Multi-signal ML models (GradientBoosting + IsolationForest)</li>
            <li>HITL triage system with 4-queue risk categorization (HIGH, MEDIUM, SHADOW IT, DATA CONFLICTS)</li>
            <li>10+ triage actions with full audit trail and state management</li>
            <li>Professional SecOps dashboard with 5-tab navigation</li>
            <li>Enterprise auto-connect to AAM for approved assets</li>
            <li>NLP query interface for asset discovery <span className="pg-status-badge pg-status-demo">Demo</span></li>
            <li>Digital twin synthetic data generation (10 archetypes)</li>
          </ul>
          
          <h4 style={{color: '#f85149'}}>Current Limitations</h4>
          <ul>
            <li>Single-tenant deployment only (no multi-tenancy yet)</li>
            <li>Connection pool contention under 50+ concurrent users</li>
            <li>Audit trail stored in files instead of database</li>
          </ul>
          
          <h4 style={{color: '#f85149'}}>NOW - Critical Path</h4>
          <ul>
            <li><strong>Supabase Migration with Multi-Tenancy:</strong> Schema evolution, Row-Level Security (RLS), tenant isolation, data migration from Neon</li>
            <li><strong>Performance Optimization:</strong> Connection pool tuning for 100+ concurrent users, query optimization, Redis caching strategy</li>
          </ul>
          
          <h4 style={{color: '#ffc107'}}>NEXT - Value-Adds</h4>
          <ul>
            <li><strong>Discovery Intelligence:</strong> Active learning from HITL feedback, Explainable AI (SHAP/LIME), advanced detection patterns</li>
            <li><strong>API & Integration:</strong> GraphQL endpoints, event streaming, platform integration hooks</li>
          </ul>
          
          <h4 style={{color: '#58a6ff'}}>LATER - Future</h4>
          <ul>
            <li><strong>UX Enhancements:</strong> Bulk triage actions, network graph visualizations, mobile-responsive design</li>
            <li><strong>Advanced Automation:</strong> Workflow hooks for platform orchestrator (defer to platform AOA)</li>
          </ul>

          <h3>AAM (Adaptive API Mesh)</h3>
          <p style={{marginBottom: '0.5rem'}}><strong>Status:</strong> <span style={{color: '#3fb950'}}>Production Ready</span></p>
          <h4 style={{color: '#3fb950'}}>Completed</h4>
          <ul>
            <li>4 production connectors (Salesforce, MongoDB, FileSource, Supabase)</li>
            <li>Canonical event normalization with Pydantic validation</li>
            <li>Schema drift detection with fingerprinting</li>
            <li>LLM-powered auto-repair with confidence scoring</li>
            <li>Safe Mode and 90% SLO targets</li>
          </ul>
          <h4 style={{color: '#58a6ff'}}>Next Steps</h4>
          <ul>
            <li>Scale to several dozen connectors to prove enterprise scalability</li>
            <li>Enhanced drift repair with multi-model LLM selection</li>
            <li>Connector marketplace for community-built integrations</li>
          </ul>

          <h3>DCL (Data Connection Layer)</h3>
          <p style={{marginBottom: '0.5rem'}}><strong>Status:</strong> <span style={{color: '#3fb950'}}>Production Ready</span></p>
          <h4 style={{color: '#3fb950'}}>Completed</h4>
          <ul>
            <li>Enterprise ontology creation and management</li>
            <li>AI-powered entity mapping with LLM + RAG</li>
            <li>Knowledge graph generation with real-time updates</li>
            <li>Multi-tenant architecture with Redis-backed state</li>
            <li>WebSocket streaming for live visualization</li>
          </ul>
          <h4 style={{color: '#58a6ff'}}>Next Steps</h4>
          <ul>
            <li>Enhanced graph visualization with filtering</li>
            <li>Graph-based query language for complex relationships</li>
            <li>Automated data lineage tracking</li>
          </ul>

          <h3>AOA (Agentic Orchestration Architecture)</h3>
          <p style={{marginBottom: '0.5rem'}}><strong>Status:</strong> <span style={{color: '#ffc107'}}>In Development</span></p>
          <h4 style={{color: '#3fb950'}}>Completed</h4>
          <ul>
            <li>Basic API endpoints (state, connect, reset)</li>
            <li>Task queue integration with Redis RQ</li>
            <li>Multi-tenant job enforcement (1 active job per tenant)</li>
            <li>AOD discovery integration for asset handoff</li>
            <li>Demo scan functionality</li>
          </ul>
          <h4 style={{color: '#ffc107'}}>In Progress</h4>
          <ul>
            <li>Multi-step workflow engine</li>
            <li>Cross-domain playbook execution (data + compute + network)</li>
            <li>Workflow state machine with error recovery</li>
            <li>Business process automation templates</li>
          </ul>
          <h4 style={{color: '#58a6ff'}}>Planned</h4>
          <ul>
            <li>Visual workflow designer</li>
            <li>Workflow versioning and rollback</li>
            <li>Advanced scheduling and triggers</li>
          </ul>

          <h3>Pre-Built AI Agents</h3>
          <p style={{marginBottom: '0.5rem'}}><strong>Status:</strong> <span style={{color: '#ffc107'}}>In Development</span></p>
          <h4 style={{color: '#3fb950'}}>Completed</h4>
          <ul>
            <li>Agent execution framework via DCL</li>
            <li>Agent context management with data access</li>
            <li>Agent metadata support (Phase 4)</li>
          </ul>
          <h4 style={{color: '#ffc107'}}>In Progress</h4>
          <ul>
            <li><strong><a href="https://autonomos.technology" style={{color: '#58a6ff', textDecoration: 'none'}}>FinOps Agent</a>:</strong> Cloud cost optimization, budget forecasting, and financial operations automation</li>
            <li><strong><a href="https://autonomos.cloud" style={{color: '#58a6ff', textDecoration: 'none'}}>RevOps Agent</a>:</strong> Revenue intelligence, pipeline analysis, and CRM workflow automation</li>
            <li>Agent-to-agent communication protocols</li>
            <li>HITL approval workflows for agent actions</li>
          </ul>
          <h4 style={{color: '#58a6ff'}}>Planned</h4>
          <ul>
            <li>Agent marketplace and custom agent builder</li>
            <li>Agent performance analytics</li>
            <li>Multi-agent swarm coordination</li>
          </ul>

          <h3>NLP / Intent (Control Center)</h3>
          <p style={{marginBottom: '0.5rem'}}><strong>Status:</strong> <span style={{color: '#ffc107'}}>In Development</span></p>
          <h4 style={{color: '#3fb950'}}>Completed</h4>
          <ul>
            <li>Persona classification (CTO, CRO, COO, CFO)</li>
            <li>Query routing to appropriate systems</li>
            <li>Persona-specific dashboard summaries <span className="pg-status-badge pg-status-demo">Demo</span></li>
            <li>Knowledge base search stubs</li>
          </ul>
          <h4 style={{color: '#ffc107'}}>In Progress</h4>
          <ul>
            <li>Production RAG knowledge base with vector search</li>
            <li>Real-time data integration for dashboard summaries</li>
            <li>Advanced intent parsing and disambiguation</li>
          </ul>
          <h4 style={{color: '#58a6ff'}}>Planned</h4>
          <ul>
            <li>Multi-turn conversation support</li>
            <li>Voice interface integration</li>
            <li>Proactive insights and recommendations</li>
            <li>Custom persona creation for domain-specific roles</li>
          </ul>

          <h3>Security & Compliance</h3>
          <p style={{marginBottom: '0.5rem'}}><strong>Status:</strong> <span style={{color: '#58a6ff'}}>Planned</span></p>
          <h4 style={{color: '#3fb950'}}>Completed</h4>
          <ul>
            <li>Multi-tenant data isolation with tenant_id scoping</li>
            <li>JWT-based authentication with Argon2 password hashing</li>
            <li>Secure credential storage for production connectors</li>
            <li>Shadow IT detection and HITL triage workflow</li>
          </ul>
          <h4 style={{color: '#58a6ff'}}>Planned</h4>
          <ul>
            <li>SOC 2 Type II compliance certification</li>
            <li>Role-based access control (RBAC) for team permissions</li>
            <li>Audit logging and compliance reporting</li>
            <li>Data encryption at rest and in transit</li>
            <li>PII detection and redaction automation</li>
            <li>Security agent for automated threat detection and response</li>
          </ul>

          <div className="pg-highlight-box" style={{marginTop: '2rem'}}>
            <p><strong>Note:</strong> Roadmap items are prioritized based on customer feedback and platform needs. Timeline details are intentionally omitted as we use an agile, priority-based approach rather than fixed schedules.</p>
          </div>
        </section>

        {/* Footer */}
        <div className="pg-section" style={{textAlign: 'center', color: '#8b949e'}}>
          <p>AutonomOS - Multi-Tenant AI Orchestration Platform</p>
          <p style={{fontSize: '0.85rem', marginTop: '0.5rem'}}>Last Updated: November 19, 2025 | Phase 4 Complete - Production Ready</p>
        </div>
      </div>
    </div>
  );
}
