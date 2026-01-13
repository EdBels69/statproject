# Stat Analyzer MVP

A rule-based statistical analysis platform for clinical research.
Combines a strictly validated Python statistical engine with a user-friendly React interface.

## Features

- **20+ Statistical Methods**: Including t-tests, ANOVA, non-parametric tests, survival analysis, regression, and ROC analysis
- **AI-Powered Protocol Design**: Automated test selection based on data characteristics
- **Interactive Wizard**: Step-by-step analysis workflow with visual feedback
- **Alpha Parameter Selection**: Customize significance level (0.01, 0.05, 0.10)
- **Quick Start Guide**: Onboarding for new users
- **Error Boundary**: Graceful error handling throughout the application
- **WCAG AA Compliance**: Accessible interface for all users
- **Export Reports**: Download HTML reports with analysis results

## Project Structure

- `backend/`: FastAPI application (Python)
  - `app/api/`: API endpoints for analysis, datasets, and quality checks
  - `app/core/`: Protocol engine, pipeline, and study designer
  - `app/stats/`: Statistical analysis engine with 20+ methods
  - `app/modules/`: Data parsing, quality checks, reporting, and text generation
  - `tests/`: Integration tests, E2E tests, and stress tests
- `frontend/`: React application (Vite + Tailwind)
  - `src/app/pages/`: Dataset list, upload, wizard, settings, and analysis pages
  - `src/app/components/`: Layout components, charts, and reusable UI elements
- `docs/`: Project documentation and specifications

## Getting Started

### Prerequisites

- Python 3.8+
- Node.js 18+
- pip (Python package manager)
- npm (Node package manager)

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The backend API will be available at `http://localhost:8000`

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend application will be available at `http://localhost:5173`

## Quick Start

1. **Upload Data**: Navigate to the Upload page and import your CSV or Excel file
2. **Select Analysis**: Use the Wizard to choose your analysis goal and variables
3. **Run Analysis**: Execute the protocol and view results with AI-generated interpretations
4. **Export Report**: Download the HTML report for documentation

## Available Statistical Methods

### Comparison Tests
- One-Sample T-Test
- Student's t-test (Independent)
- Welch's T-Test
- Mann-Whitney U Test
- Paired t-test
- Wilcoxon Signed-Rank Test

### Multi-Group Tests
- One-Way ANOVA
- Welch's ANOVA
- Kruskal-Wallis H-test
- Repeated Measures ANOVA
- Friedman Test

### Categorical Tests
- Chi-Square Test of Independence
- Fisher's Exact Test

### Correlation
- Pearson Correlation
- Spearman Correlation

### Advanced Analysis
- Linear Mixed Models (LMM)
- Linear Regression
- Logistic Regression
- ROC Analysis
- Kaplan-Meier Survival Analysis

## API Documentation

Once the backend is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Testing

### Run All Tests
```bash
cd backend
python -m pytest tests/
```

### Run Specific Tests
```bash
# Full flow integration test
python tests/test_full_flow.py

# E2E test (Upload → Analyze → Export)
python tests/test_e2e_upload_analyze_export.py

# Stress test (all 20 methods)
python tests/test_stress_all_methods.py
```

## Settings

Configure analysis parameters via the Settings page:
- **Alpha Level**: Set significance threshold (0.01, 0.05, or 0.10)
- Settings are persisted in localStorage

## Error Handling

The application includes an Error Boundary component that:
- Catches and displays runtime errors gracefully
- Provides options to return home or reload the page
- Shows error details for debugging

## Accessibility

The interface follows WCAG AA guidelines with:
- ARIA labels and roles
- Keyboard navigation support
- Focus indicators
- Semantic HTML structure
- Screen reader compatibility

## Docker Deployment

### Quick Deploy

```bash
# Deploy the application with one command
./deploy.sh

# Stop the application
./stop.sh

# Restart the application
./restart.sh
```

### Using Docker Compose

```bash
docker-compose up -d
```

### Building Individual Services

```bash
# Backend
cd backend
docker build -t stat-analyzer-backend .

# Frontend
cd frontend
docker build -t stat-analyzer-frontend .
```

### Production Deployment

For detailed deployment instructions, including SSL configuration, monitoring, and scaling, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Development

### Backend Architecture

- **FastAPI**: Modern async web framework
- **Pydantic**: Data validation with schemas
- **Pandas**: Data manipulation and analysis
- **SciPy/Statsmodels**: Statistical computations
- **Matplotlib/Plotly**: Visualization

### Frontend Stack

- **React**: UI framework
- **Vite**: Build tool and dev server
- **Tailwind CSS**: Utility-first styling
- **React Router**: Client-side routing
- **Heroicons**: Icon library

## License

See LICENSE file for details.

## Support

For issues and questions, please refer to the documentation in the `docs/` directory or contact the development team.
