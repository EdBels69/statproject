"""
Clustered Correlation Engine
============================
jYS-style hierarchical clustering on correlation matrices.
Produces reordered heatmaps with dendrogram and cluster identification.
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Literal, Optional
from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
from scipy.spatial.distance import squareform
from scipy import stats
import gc


class ClusteredCorrelationEngine:
    """
    Computes correlation matrix, applies hierarchical clustering,
    reorders by dendrogram, and identifies variable clusters.
    
    Similar to jYS module in JAMOVI.
    """
    
    def analyze(
        self,
        df: pd.DataFrame,
        variables: List[str],
        method: Literal["pearson", "spearman"] = "pearson",
        linkage_method: Literal["ward", "complete", "average", "single"] = "ward",
        n_clusters: Optional[int] = None,
        distance_threshold: Optional[float] = None,
        show_p_values: bool = True,
        alpha: float = 0.05,
        auto_method: Literal["elbow", "silhouette"] = "elbow"
    ) -> Dict[str, Any]:
        """
        Compute clustered correlation matrix.
        
        Parameters
        ----------
        variables : List[str]
            Column names to include in correlation matrix
        method : str
            Correlation method: 'pearson' or 'spearman'
        linkage_method : str
            Hierarchical clustering linkage: 'ward', 'complete', 'average', 'single'
        n_clusters : int, optional
            Number of clusters to extract (auto-detect if None)
        distance_threshold : float, optional
            Alternative to n_clusters: use distance threshold
        show_p_values : bool
            Calculate p-values for correlations
        alpha : float
            Significance level for p-value flagging
        auto_method : str
            Auto-detection method: 'elbow' (fast, default) or 'silhouette' (more accurate, requires sklearn)
        
        Returns
        -------
        Dict with correlation matrix, clusters, dendrogram data, and submatrices
        """
        # 1. Filter and clean data
        data = df[variables].dropna()
        n_obs = len(data)
        
        if n_obs < 3:
            return {"error": "Insufficient data (need at least 3 observations)"}
        
        if len(variables) < 2:
            return {"error": "Need at least 2 variables for correlation"}
        
        # 2. Compute correlation matrix
        if method == "pearson":
            corr_matrix = data.corr(method="pearson")
        else:
            corr_matrix = data.corr(method="spearman")
        
        # 3. Compute p-values if requested
        p_matrix = None
        if show_p_values:
            p_matrix = self._compute_p_values(data, variables, method)
        
        # 4. Convert to distance matrix for clustering
        # Distance = 1 - |correlation|
        corr_values = corr_matrix.values.copy()
        dist_matrix = 1 - np.abs(corr_values)
        np.fill_diagonal(dist_matrix, 0)
        
        # Handle any NaN values
        dist_matrix = np.nan_to_num(dist_matrix, nan=1.0)
        
        # Store for silhouette calculation
        self._dist_matrix = dist_matrix
        
        # 5. Hierarchical clustering
        try:
            condensed_dist = squareform(dist_matrix)
            Z = linkage(condensed_dist, method=linkage_method)
        except Exception as e:
            return {"error": f"Clustering failed: {str(e)}"}
        
        # 6. Get dendrogram ordering
        dendro = dendrogram(Z, no_plot=True, labels=variables)
        reorder_idx = dendro['leaves']
        reordered_vars = [variables[i] for i in reorder_idx]
        
        # 7. Reorder correlation matrix
        reordered_corr = corr_matrix.iloc[reorder_idx, reorder_idx]
        
        # 8. Assign clusters
        if n_clusters is None and distance_threshold is None:
            n_clusters = self._auto_detect_clusters(Z, len(variables), auto_method)
        
        if n_clusters:
            cluster_labels = fcluster(Z, n_clusters, criterion='maxclust')
        else:
            cluster_labels = fcluster(Z, distance_threshold, criterion='distance')
        
        # Map labels to original variable order, then to reordered
        reordered_labels = [int(cluster_labels[i]) for i in reorder_idx]
        
        # Create cluster_assignments dict (original order)
        cluster_assignments = {var: int(cluster_labels[i]) for i, var in enumerate(variables)}
        
        # 9. Extract submatrices per cluster
        submatrices = self._extract_submatrices(
            reordered_corr, reordered_vars, reordered_labels, p_matrix, reorder_idx, alpha
        )
        
        # 10. Prepare output
        result = {
            "method": method,
            "linkage": linkage_method,
            "n_observations": n_obs,
            "n_variables": len(variables),
            "n_clusters": len(set(reordered_labels)),
            
            # Reordered correlation matrix
            "correlation_matrix": {
                "variables": reordered_vars,
                "values": reordered_corr.values.tolist()
            },
            
            # Original order (for reference)
            "original_order": variables,
            
            # Cluster assignments (dict: variable -> cluster_id)
            "cluster_assignments": cluster_assignments,
            
            # Cluster assignments
            "clusters": [
                {
                    "id": cid,
                    "variables": [v for v, l in zip(reordered_vars, reordered_labels) if l == cid],
                    "color": self._cluster_color(cid),
                    "n_variables": sum(1 for l in reordered_labels if l == cid)
                }
                for cid in sorted(set(reordered_labels))
            ],
            
            # Submatrices
            "submatrices": submatrices,
            
            # Dendrogram data for visualization
            "dendrogram": {
                "labels": reordered_vars,
                "icoord": [list(x) for x in dendro["icoord"]],
                "dcoord": [list(x) for x in dendro["dcoord"]],
                "leaves": reorder_idx
            },
            
            # Heatmap data (for easy frontend rendering)
            "heatmap_data": [
                {
                    "row": i,
                    "col": j,
                    "row_var": reordered_vars[i],
                    "col_var": reordered_vars[j],
                    "r": float(reordered_corr.iloc[i, j]),
                    "p": float(p_matrix.iloc[reorder_idx[i], reorder_idx[j]]) if p_matrix is not None else None,
                    "significant": p_matrix.iloc[reorder_idx[i], reorder_idx[j]] < alpha if p_matrix is not None else None
                }
                for i in range(len(reordered_vars))
                for j in range(len(reordered_vars))
            ]
        }
        
        gc.collect()
        return result
    
    def _compute_p_values(
        self, 
        data: pd.DataFrame, 
        variables: List[str], 
        method: str
    ) -> pd.DataFrame:
        """Compute p-value matrix for correlations"""
        n = len(variables)
        p_matrix = pd.DataFrame(
            np.ones((n, n)), 
            index=variables, 
            columns=variables
        )
        
        for i in range(n):
            for j in range(i + 1, n):
                x = data[variables[i]].dropna()
                y = data[variables[j]].dropna()
                
                # Align indices
                common = x.index.intersection(y.index)
                x = x.loc[common]
                y = y.loc[common]
                
                if len(common) >= 3:
                    if method == "pearson":
                        _, p = stats.pearsonr(x, y)
                    else:
                        _, p = stats.spearmanr(x, y)
                    
                    p_matrix.iloc[i, j] = p
                    p_matrix.iloc[j, i] = p
        
        return p_matrix
    
    def _auto_detect_clusters(self, Z, n_vars: int, auto_method: str = "elbow") -> int:
        """
        Data-driven automatic cluster count detection.
        
        Parameters
        ----------
        Z : ndarray
            Linkage matrix from hierarchical clustering
        n_vars : int
            Number of variables
        auto_method : str
            'elbow' (fast, default) or 'silhouette' (more accurate, requires sklearn)
        
        Returns
        -------
        int : Optimal number of clusters
        """
        if n_vars < 2:
            return 1
        
        if auto_method == "silhouette":
            return self._auto_detect_silhouette(Z, n_vars)
        else:
            return self._auto_detect_elbow(Z, n_vars)
    
    def _auto_detect_elbow(self, Z, n_vars: int) -> int:
        """Elbow method using maximum linkage distance jump."""
        distances = Z[:, 2]
        
        if len(distances) < 2:
            return max(1, n_vars // 2)
        
        diffs = np.diff(distances)
        if len(diffs) == 0:
            return max(2, min(n_vars, 6))
        
        max_diff_idx = np.argmax(diffs)
        n_clusters = n_vars - max_diff_idx
        
        n_clusters = max(2, min(n_clusters, n_vars))
        
        return int(n_clusters)
    
    def _auto_detect_silhouette(self, Z, n_vars: int) -> int:
        """Silhouette-based auto-detection (more accurate but requires sklearn)."""
        try:
            from sklearn.metrics import silhouette_score
            from scipy.cluster.hierarchy import fcluster
        except ImportError:
            # Fallback to elbow if sklearn not available
            return self._auto_detect_elbow(Z, n_vars)
        
        if not hasattr(self, '_dist_matrix'):
            # Fallback if distance matrix not stored
            return self._auto_detect_elbow(Z, n_vars)
        
        best_score = -1
        best_k = 2
        
        # Try different cluster counts
        for k in range(2, min(n_vars, 8)):
            try:
                labels = fcluster(Z, k, criterion='maxclust')
                score = silhouette_score(self._dist_matrix, labels, metric='precomputed')
                
                if score > best_score:
                    best_score = score
                    best_k = k
            except:
                continue
        
        return best_k

    
    def _extract_submatrices(
        self,
        corr: pd.DataFrame,
        vars: List[str],
        labels: List[int],
        p_matrix: Optional[pd.DataFrame],
        reorder_idx: List[int],
        alpha: float
    ) -> List[Dict]:
        """Extract correlation submatrices for each cluster"""
        submatrices = []
        
        for cid in sorted(set(labels)):
            cluster_vars = [v for v, l in zip(vars, labels) if l == cid]
            
            if len(cluster_vars) >= 2:
                sub_corr = corr.loc[cluster_vars, cluster_vars]
                
                # Calculate mean correlation within cluster
                upper_tri = np.triu_indices(len(cluster_vars), k=1)
                corr_values = sub_corr.values[upper_tri]
                mean_r = float(np.mean(np.abs(corr_values)))
                
                # Prepare matrix with significance markers
                matrix_data = []
                for i, v1 in enumerate(cluster_vars):
                    row = []
                    for j, v2 in enumerate(cluster_vars):
                        r = float(sub_corr.loc[v1, v2])
                        cell = {"r": r}
                        row.append(cell)
                    matrix_data.append(row)
                
                submatrices.append({
                    "cluster_id": cid,
                    "variables": cluster_vars,
                    "n_variables": len(cluster_vars),
                    "matrix": sub_corr.values.tolist(),
                    "mean_abs_correlation": mean_r,
                    "interpretation": self._interpret_cluster(cluster_vars, mean_r)
                })
        
        return submatrices
    
    def _interpret_cluster(self, variables: List[str], mean_r: float) -> str:
        """Generate interpretation for cluster"""
        strength = "сильная" if mean_r > 0.7 else "умеренная" if mean_r > 0.4 else "слабая"
        return (
            f"Кластер из {len(variables)} переменных со средней "
            f"{strength} корреляцией (r̄={mean_r:.2f})"
        )
    
    def _cluster_color(self, cid: int) -> str:
        """Assign color to cluster"""
        colors = [
            "#3b82f6",  # blue
            "#ef4444",  # red
            "#22c55e",  # green
            "#f59e0b",  # amber
            "#8b5cf6",  # violet
            "#ec4899",  # pink
            "#06b6d4",  # cyan
            "#84cc16",  # lime
        ]
        return colors[(cid - 1) % len(colors)]


# Convenience function
def run_clustered_correlation(
    df: pd.DataFrame,
    variables: List[str],
    method: str = "pearson",
    n_clusters: int = None
) -> Dict[str, Any]:
    """
    Quick function to run clustered correlation analysis.
    
    Example
    -------
    >>> result = run_clustered_correlation(
    ...     df, 
    ...     variables=["V1", "V2", "V3", "V4", "V5"],
    ...     method="spearman"
    ... )
    >>> print(result["n_clusters"])
    2
    """
    engine = ClusteredCorrelationEngine()
    return engine.analyze(df, variables, method=method, n_clusters=n_clusters)
