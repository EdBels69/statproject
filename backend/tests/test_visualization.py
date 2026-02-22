"""
Tests for Visualization Standards (v1.1)
"""

import pytest
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from app.modules.plot_templates import (
    plot_group_comparison,
    plot_correlation_matrix,
    plot_distribution,
    plot_regression
)
from app.modules.plot_config import apply_publication_config, PUBLICATION_CONFIG

class TestVisualization:
    
    @pytest.fixture
    def sample_data(self):
        np.random.seed(42)
        df = pd.DataFrame({
            'Group': np.random.choice(['A', 'B', 'C'], 100),
            'Value': np.random.normal(loc=10, scale=2, size=100),
            'Age': np.random.randint(20, 80, 100),
            'Score': np.random.uniform(0, 100, 100)
        })
        # Add correlation
        df['Score'] = df['Age'] * 0.5 + np.random.normal(0, 10, 100)
        return df

    def test_config_application(self):
        """Test that configuration is applied correctly."""
        apply_publication_config()
        # Check a few key settings
        assert plt.rcParams['figure.dpi'] == PUBLICATION_CONFIG['figure.dpi']
        assert plt.rcParams['font.family'] == [PUBLICATION_CONFIG['font.family']]

    def test_plot_group_comparison(self, sample_data, tmp_path):
        """Test boxplot generation."""
        output_dir = str(tmp_path)
        path = plot_group_comparison(
            sample_data, 'Group', 'Value', output_dir, 
            filename="test_box", title="Test Boxplot"
        )
        
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0
        assert path.endswith(".png")

    def test_plot_correlation_matrix(self, sample_data, tmp_path):
        """Test heatmap generation."""
        output_dir = str(tmp_path)
        corr = sample_data[['Value', 'Age', 'Score']].corr()
        path = plot_correlation_matrix(
            corr, output_dir, 
            filename="test_corr", title="Test Corr"
        )
        
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0

    def test_plot_distribution(self, sample_data, tmp_path):
        """Test distribution plot."""
        output_dir = str(tmp_path)
        path = plot_distribution(
            sample_data, 'Value', output_dir,
            filename="test_dist"
        )
        
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0

    def test_plot_regression(self, sample_data, tmp_path):
        """Test regression plot."""
        output_dir = str(tmp_path)
        path = plot_regression(
            sample_data, 'Age', 'Score', output_dir,
            filename="test_reg"
        )
        
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
