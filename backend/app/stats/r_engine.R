#!/usr/bin/env Rscript

suppressWarnings({
  library(jsonlite)
  library(stats)
  library(survival)
  library(pROC)
  library(lme4)
  library(lmerTest)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) {
  quit(status = 2)
}

input_path <- args[1]
output_path <- args[2]

payload <- fromJSON(input_path)
data_path <- payload$data_path
method_id <- as.character(payload$method_id)
col_a <- as.character(payload$col_a)
col_b <- as.character(payload$col_b)
alpha <- ifelse(is.null(payload$alpha), 0.05, as.numeric(payload$alpha))
alternative <- ifelse(is.null(payload$alternative), "two-sided", as.character(payload$alternative))
plot_engine <- ifelse(is.null(payload$plot_engine), "python", as.character(payload$plot_engine))
plot_path <- ifelse(is.null(payload$plot_path), "", as.character(payload$plot_path))

data <- read.csv(data_path, stringsAsFactors = FALSE, check.names = FALSE)

numeric_cols <- payload$numeric_cols
if (!is.null(numeric_cols) && length(numeric_cols) > 0) {
  for (c in numeric_cols) {
    if (c %in% names(data)) {
      data[[c]] <- suppressWarnings(as.numeric(data[[c]]))
    }
  }
}

force_factor_cols <- payload$force_factor_cols
if (!is.null(force_factor_cols) && length(force_factor_cols) > 0) {
  for (c in force_factor_cols) {
    if (c %in% names(data)) {
      data[[c]] <- as.factor(data[[c]])
    }
  }
}

result <- list(status = "ok", method = method_id)

safe_complete <- function(cols) {
  cols <- cols[cols %in% names(data)]
  if (length(cols) == 0) {
    return(data[0, , drop = FALSE])
  }
  data[complete.cases(data[, cols, drop = FALSE]), , drop = FALSE]
}

cohen_d_ind <- function(x, y) {
  x <- x[is.finite(x)]
  y <- y[is.finite(y)]
  if (length(x) < 2 || length(y) < 2) return(NA)
  n1 <- length(x)
  n2 <- length(y)
  s1 <- sd(x)
  s2 <- sd(y)
  if (!is.finite(s1) || !is.finite(s2)) return(NA)
  sp <- sqrt(((n1 - 1) * s1^2 + (n2 - 1) * s2^2) / (n1 + n2 - 2))
  if (!is.finite(sp) || sp == 0) return(NA)
  (mean(x) - mean(y)) / sp
}

cohen_d_paired <- function(x, y) {
  d <- y - x
  d <- d[is.finite(d)]
  if (length(d) < 2) return(NA)
  sd_d <- sd(d)
  if (!is.finite(sd_d) || sd_d == 0) return(NA)
  mean(d) / sd_d
}

cramers_v <- function(tbl) {
  if (is.null(tbl) || length(tbl) == 0) return(NA)
  chi <- suppressWarnings(chisq.test(tbl, correct = FALSE))
  n <- sum(tbl)
  r <- nrow(tbl)
  c <- ncol(tbl)
  if (n == 0) return(NA)
  v <- sqrt(as.numeric(chi$statistic) / (n * (min(r - 1, c - 1))))
  v
}

group_palette <- c("#4269d0", "#ef9154", "#4ca858", "#db4949", "#8b5cf6", "#14b8a6", "#f59e0b", "#6366f1")
pick_palette <- function(n) {
  if (n <= length(group_palette)) {
    return(group_palette[1:n])
  }
  return(colorRampPalette(group_palette)(n))
}

base_theme <- function() {
  theme_minimal(base_size = 12, base_family = "Arial") +
    theme(
      panel.grid.minor = element_blank(),
      panel.grid.major.x = element_blank(),
      panel.grid.major.y = element_line(color = "#94a3b8", linewidth = 0.3),
      axis.text = element_text(color = "#64748b"),
      axis.title = element_text(color = "#0f172a"),
      plot.title = element_text(size = 12, face = "plain"),
      legend.title = element_blank()
    )
}

matrix_to_rows <- function(m) {
  if (is.null(m) || is.null(nrow(m)) || nrow(m) == 0) {
    return(list())
  }
  out <- vector("list", nrow(m))
  for (i in seq_len(nrow(m))) {
    out[[i]] <- as.list(as.numeric(m[i, ]))
  }
  out
}

try({
  do_plot <- (!is.null(plot_path) && nchar(plot_path) > 0 && plot_engine == "r")
  if (do_plot) {
    tryCatch({
      suppressWarnings(library(ggplot2))
    }, error = function(e) {
      do_plot <<- FALSE
    })
  }

  if (method_id %in% c("t_test_ind", "t_test_welch", "t_test_rel", "t_test_one")) {
    if (method_id == "t_test_one") {
      df <- safe_complete(c(col_a))
      x <- df[[col_a]]
      mu <- ifelse(is.null(payload$mu), 0, as.numeric(payload$mu))
      tt <- t.test(x, mu = mu, alternative = alternative)
      result$stat_value <- unname(tt$statistic)
      result$p_value <- unname(tt$p.value)
    } else if (method_id == "t_test_rel") {
      df <- safe_complete(c(col_a, col_b))
      x <- df[[col_a]]
      y <- df[[col_b]]
      tt <- t.test(x, y, paired = TRUE, alternative = alternative)
      result$stat_value <- unname(tt$statistic)
      result$p_value <- unname(tt$p.value)
      d <- cohen_d_paired(x, y)
      if (is.finite(d)) {
        result$effect_size <- d
        result$effect_size_name <- "cohen-d"
      }
    } else {
      df <- safe_complete(c(col_a, col_b))
      g <- as.factor(df[[col_b]])
      x <- df[[col_a]]
      tt <- t.test(x ~ g, var.equal = (method_id == "t_test_ind"), alternative = alternative)
      result$stat_value <- unname(tt$statistic)
      result$p_value <- unname(tt$p.value)
      levels_g <- levels(g)
      if (length(levels_g) == 2) {
        d <- cohen_d_ind(x[g == levels_g[1]], x[g == levels_g[2]])
        if (is.finite(d)) {
          result$effect_size <- d
          result$effect_size_name <- "cohen-d"
        }
      }
      if (do_plot) {
        pal <- pick_palette(length(levels_g))
        p <- ggplot(df, aes_string(x = col_b, y = col_a, color = col_b)) +
          geom_boxplot(outlier.shape = NA, alpha = 0.4) +
          geom_jitter(width = 0.15, size = 1.2, alpha = 0.5) +
          scale_color_manual(values = pal) +
          base_theme() +
          theme(legend.position = "none") +
          labs(x = col_b, y = col_a, title = col_a)
        ggsave(plot_path, p, width = 7, height = 4.5, dpi = 300)
        result$plot_path <- plot_path
      }
    }
  } else if (method_id %in% c("mann_whitney", "wilcoxon")) {
    df <- safe_complete(c(col_a, col_b))
    if (method_id == "mann_whitney") {
      g <- as.factor(df[[col_b]])
      x <- df[[col_a]]
      wt <- wilcox.test(x ~ g, alternative = alternative, exact = FALSE)
      result$stat_value <- unname(wt$statistic)
      result$p_value <- unname(wt$p.value)
    } else {
      x <- df[[col_a]]
      y <- df[[col_b]]
      wt <- wilcox.test(x, y, paired = TRUE, alternative = alternative, exact = FALSE)
      result$stat_value <- unname(wt$statistic)
      result$p_value <- unname(wt$p.value)
    }
    if (do_plot && method_id == "mann_whitney") {
      pal <- pick_palette(length(levels(g)))
      p <- ggplot(df, aes_string(x = col_b, y = col_a, color = col_b)) +
        geom_boxplot(outlier.shape = NA, alpha = 0.4) +
        geom_jitter(width = 0.15, size = 1.2, alpha = 0.5) +
        scale_color_manual(values = pal) +
        base_theme() +
        theme(legend.position = "none") +
        labs(x = col_b, y = col_a, title = col_a)
      ggsave(plot_path, p, width = 7, height = 4.5, dpi = 300)
      result$plot_path <- plot_path
    }
  } else if (method_id %in% c("anova", "anova_welch")) {
    df <- safe_complete(c(col_a, col_b))
    g <- as.factor(df[[col_b]])
    y <- df[[col_a]]
    if (method_id == "anova") {
      fit <- aov(y ~ g, data = df)
      s <- summary(fit)
      result$stat_value <- unname(s[[1]]$`F value`[1])
      result$p_value <- unname(s[[1]]$`Pr(>F)`[1])
    } else {
      wt <- oneway.test(y ~ g, data = df, var.equal = FALSE)
      result$stat_value <- unname(wt$statistic)
      result$p_value <- unname(wt$p.value)
    }
    if (do_plot) {
      pal <- pick_palette(length(levels(g)))
      p <- ggplot(df, aes_string(x = col_b, y = col_a, color = col_b)) +
        geom_boxplot(outlier.shape = NA, alpha = 0.4) +
        geom_jitter(width = 0.15, size = 1.2, alpha = 0.5) +
        scale_color_manual(values = pal) +
        base_theme() +
        theme(legend.position = "none") +
        labs(x = col_b, y = col_a, title = col_a)
      ggsave(plot_path, p, width = 7, height = 4.5, dpi = 300)
      result$plot_path <- plot_path
    }
  } else if (method_id == "kruskal") {
    df <- safe_complete(c(col_a, col_b))
    g <- as.factor(df[[col_b]])
    y <- df[[col_a]]
    kt <- kruskal.test(y ~ g, data = df)
    result$stat_value <- unname(kt$statistic)
    result$p_value <- unname(kt$p.value)
    if (do_plot) {
      pal <- pick_palette(length(levels(g)))
      p <- ggplot(df, aes_string(x = col_b, y = col_a, color = col_b)) +
        geom_boxplot(outlier.shape = NA, alpha = 0.4) +
        geom_jitter(width = 0.15, size = 1.2, alpha = 0.5) +
        scale_color_manual(values = pal) +
        base_theme() +
        theme(legend.position = "none") +
        labs(x = col_b, y = col_a, title = col_a)
      ggsave(plot_path, p, width = 7, height = 4.5, dpi = 300)
      result$plot_path <- plot_path
    }
  } else if (method_id %in% c("chi_square", "fisher", "fisher_exact")) {
    df <- safe_complete(c(col_a, col_b))
    tbl <- table(df[[col_a]], df[[col_b]])
    if (method_id == "chi_square") {
      cs <- suppressWarnings(chisq.test(tbl, correct = FALSE))
      result$stat_value <- unname(cs$statistic)
      result$p_value <- unname(cs$p.value)
      v <- cramers_v(tbl)
      if (is.finite(v)) {
        result$effect_size <- v
        result$effect_size_name <- "cramers_v"
      }
    } else {
      ft <- fisher.test(tbl)
      result$stat_value <- unname(ft$statistic)
      result$p_value <- unname(ft$p.value)
    }
    if (do_plot) {
      props <- prop.table(tbl, margin = 2)
      long <- as.data.frame(props)
      colnames(long) <- c("Category", "Group", "Prop")
      pal <- pick_palette(length(unique(long$Category)))
      p <- ggplot(long, aes(x = Group, y = Prop, fill = Category)) +
        geom_col(position = "stack") +
        scale_fill_manual(values = pal) +
        base_theme() +
        theme(legend.position = "right") +
        labs(x = col_b, y = "Proportion", title = col_a)
      ggsave(plot_path, p, width = 7, height = 4.5, dpi = 300)
      result$plot_path <- plot_path
    }
  } else if (method_id %in% c("pearson", "spearman")) {
    df <- safe_complete(c(col_a, col_b))
    x <- df[[col_a]]
    y <- df[[col_b]]
    ct <- cor.test(x, y, method = method_id)
    result$stat_value <- unname(ct$statistic)
    result$p_value <- unname(ct$p.value)
    if (!is.null(ct$estimate)) {
      est <- unname(ct$estimate)
      if (is.finite(est)) {
        result$effect_size <- est
        result$effect_size_name <- "r"
      }
    }
    if (do_plot) {
      df_plot <- df[complete.cases(df[, c(col_a, col_b), drop = FALSE]), , drop = FALSE]
      pal <- pick_palette(2)
      p <- ggplot(df_plot, aes_string(x = col_a, y = col_b)) +
        geom_point(color = pal[1], alpha = 0.6, size = 1.4) +
        geom_smooth(method = "lm", se = TRUE, color = pal[2], linewidth = 0.9) +
        base_theme() +
        labs(x = col_a, y = col_b, title = paste(col_a, "vs", col_b))
      ggsave(plot_path, p, width = 7, height = 4.5, dpi = 300)
      result$plot_path <- plot_path
    }
  } else if (method_id %in% c("linear_regression", "logistic_regression")) {
    predictors <- payload$predictors
    predictors <- predictors[predictors %in% names(data)]
    if (length(predictors) == 0) predictors <- c(col_b)
    df <- safe_complete(c(col_a, predictors))
    if (method_id == "linear_regression") {
      formula <- as.formula(paste(col_a, "~", paste(predictors, collapse = "+")))
      fit <- lm(formula, data = df)
      s <- summary(fit)
      if (!is.null(s$fstatistic)) {
        fstat <- s$fstatistic[1]
        df1 <- s$fstatistic[2]
        df2 <- s$fstatistic[3]
        pval <- pf(fstat, df1, df2, lower.tail = FALSE)
        result$stat_value <- unname(fstat)
        result$p_value <- unname(pval)
      }
      result$r_squared <- unname(s$r.squared)
    } else {
      formula <- as.formula(paste(col_a, "~", paste(predictors, collapse = "+")))
      fit <- glm(formula, data = df, family = binomial())
      fit0 <- glm(as.formula(paste(col_a, "~ 1")), data = df, family = binomial())
      lr <- anova(fit0, fit, test = "Chisq")
      if (nrow(lr) >= 2) {
        result$stat_value <- unname(lr$Deviance[2])
        result$p_value <- unname(lr$`Pr(>Chi)`[2])
      }
    }
    if (do_plot && length(predictors) == 1) {
      pred <- predictors[1]
      if (!is.null(pred) && pred %in% names(df)) {
        df_plot <- df[complete.cases(df[, c(col_a, pred), drop = FALSE]), , drop = FALSE]
        pal <- pick_palette(2)
        if (method_id == "linear_regression") {
          if (is.numeric(df_plot[[pred]]) && is.numeric(df_plot[[col_a]])) {
            p <- ggplot(df_plot, aes_string(x = pred, y = col_a)) +
              geom_point(color = pal[1], alpha = 0.6, size = 1.4) +
              geom_smooth(method = "lm", se = TRUE, color = pal[2], linewidth = 0.9) +
              base_theme() +
              labs(x = pred, y = col_a, title = paste(col_a, "vs", pred))
            ggsave(plot_path, p, width = 7, height = 4.5, dpi = 300)
            result$plot_path <- plot_path
          }
        } else {
          y_vals <- df_plot[[col_a]]
          if (!is.numeric(y_vals)) {
            y_vals <- as.numeric(as.factor(y_vals)) - 1
            df_plot$y_plot <- y_vals
          } else {
            df_plot$y_plot <- y_vals
          }
          if (is.numeric(df_plot[[pred]])) {
            p <- ggplot(df_plot, aes_string(x = pred, y = "y_plot")) +
              geom_jitter(height = 0.05, width = 0, alpha = 0.4, color = pal[1]) +
              geom_smooth(method = "glm", method.args = list(family = "binomial"), se = TRUE, color = pal[2], linewidth = 0.9) +
              scale_y_continuous(breaks = c(0, 1), limits = c(-0.05, 1.05)) +
              base_theme() +
              labs(x = pred, y = col_a, title = paste(col_a, "vs", pred))
            ggsave(plot_path, p, width = 7, height = 4.5, dpi = 300)
            result$plot_path <- plot_path
          }
        }
      }
    }
  } else if (method_id == "roc_analysis") {
    df <- safe_complete(c(col_a, col_b))
    # Keep semantics aligned with python engine:
    # col_a = score (numeric), col_b = label (binary).
    y <- df[[col_b]]
    score <- df[[col_a]]
    roc_obj <- roc(y, score, quiet = TRUE)
    result$roc_auc <- as.numeric(auc(roc_obj))
  } else if (method_id == "survival_km") {
    df <- safe_complete(c(col_a, col_b))
    group_col <- payload$group_col
    if (!is.null(group_col) && group_col %in% names(df)) {
      surv <- Surv(df[[col_a]], df[[col_b]])
      fit <- survdiff(surv ~ df[[group_col]], data = df)
      chi <- fit$chisq
      df_deg <- max(1, length(fit$n) - 1)
      pval <- pchisq(chi, df = df_deg, lower.tail = FALSE)
      result$stat_value <- unname(chi)
      result$p_value <- unname(pval)
    }
  } else if (method_id == "anova_twoway") {
    group1 <- as.character(col_b)
    group2 <- as.character(payload$group2)
    df <- safe_complete(c(col_a, group1, group2))
    if (!is.null(group1) && !is.null(group2) && group1 %in% names(df) && group2 %in% names(df)) {
      df[[group1]] <- as.factor(df[[group1]])
      df[[group2]] <- as.factor(df[[group2]])

      fit <- aov(as.formula(paste(col_a, "~", group1, "*", group2)), data = df)
      s <- summary(fit)
      tab <- s[[1]]

      pick_row <- function(name) {
        if (is.null(tab) || is.null(rownames(tab))) return(NULL)
        idx <- which(rownames(tab) == name)
        if (length(idx) == 0) return(NULL)
        tab[idx[1], , drop = FALSE]
      }

      row_a <- pick_row(group1)
      row_b <- pick_row(group2)
      row_ab <- pick_row(paste(group1, group2, sep = ":"))
      if (is.null(row_ab)) {
        row_ab <- pick_row(paste(group2, group1, sep = ":"))
      }

      to_effect <- function(row) {
        if (is.null(row)) {
          return(list(stat_value = NULL, p_value = NULL, significant = FALSE))
        }
        f <- row[1, "F value"]
        p <- row[1, "Pr(>F)"]
        p_num <- ifelse(is.null(p) || is.na(p), NA, as.numeric(p))
        list(
          stat_value = ifelse(is.null(f) || is.na(f), NULL, as.numeric(f)),
          p_value = ifelse(is.na(p_num), NULL, p_num),
          significant = ifelse(is.na(p_num), FALSE, p_num < alpha)
        )
      }

      eff_a <- to_effect(row_a)
      eff_b <- to_effect(row_b)
      eff_ab <- to_effect(row_ab)

      pvals <- c(eff_a$p_value, eff_b$p_value, eff_ab$p_value)
      pvals <- pvals[!is.na(pvals)]
      fvals <- c(eff_a$stat_value, eff_b$stat_value, eff_ab$stat_value)
      fvals <- fvals[!is.na(fvals)]

      if (length(pvals) > 0) {
        result$p_value <- min(pvals)
      }
      if (length(fvals) > 0) {
        result$stat_value <- max(fvals)
      }
      result$effects <- list(
        factor_a = eff_a,
        factor_b = eff_b,
        interaction = eff_ab
      )
    }
  } else if (method_id == "clustered_correlation") {
    variables <- payload$variables
    if (is.null(variables) || length(variables) < 2) {
      variables <- c(col_a, col_b)
    }
    variables <- unique(as.character(unlist(variables)))
    variables <- variables[variables %in% names(data)]

    if (length(variables) >= 2) {
      df <- data[, variables, drop = FALSE]
      df <- df[complete.cases(df), , drop = FALSE]

      if (nrow(df) >= 3) {
        corr_method <- ifelse(is.null(payload$cluster_method), "pearson", as.character(payload$cluster_method))
        if (!corr_method %in% c("pearson", "spearman")) {
          corr_method <- "pearson"
        }

        linkage_raw <- ifelse(is.null(payload$linkage_method), "ward", as.character(payload$linkage_method))
        linkage_mapped <- linkage_raw
        if (linkage_raw == "ward") linkage_mapped <- "ward.D2"
        if (!linkage_mapped %in% c("ward.D", "ward.D2", "complete", "average", "single", "mcquitty", "median", "centroid")) {
          linkage_mapped <- "ward.D2"
          linkage_raw <- "ward"
        }

        show_p_values <- ifelse(is.null(payload$show_p_values), TRUE, as.logical(payload$show_p_values))

        corr_matrix <- suppressWarnings(cor(df, method = corr_method, use = "pairwise.complete.obs"))
        corr_matrix[!is.finite(corr_matrix)] <- 0
        diag(corr_matrix) <- 1
        colnames(corr_matrix) <- variables
        rownames(corr_matrix) <- variables

        n_vars <- length(variables)
        p_matrix <- matrix(NA_real_, nrow = n_vars, ncol = n_vars, dimnames = list(variables, variables))
        diag(p_matrix) <- 0
        if (show_p_values) {
          p_matrix[,] <- 1
          diag(p_matrix) <- 0
          for (i in seq_len(n_vars)) {
            if (i >= n_vars) break
            for (j in (i + 1):n_vars) {
              test <- tryCatch(
                suppressWarnings(cor.test(df[[variables[i]]], df[[variables[j]]], method = corr_method)),
                error = function(e) NULL
              )
              p <- if (!is.null(test) && !is.null(test$p.value)) as.numeric(test$p.value) else NA_real_
              p_matrix[i, j] <- p
              p_matrix[j, i] <- p
            }
          }
        }

        dist_matrix <- 1 - abs(corr_matrix)
        dist_matrix[!is.finite(dist_matrix)] <- 1
        diag(dist_matrix) <- 0
        hc <- hclust(as.dist(dist_matrix), method = linkage_mapped)
        reorder_idx <- hc$order
        reordered_vars <- variables[reorder_idx]
        reordered_corr <- corr_matrix[reorder_idx, reorder_idx, drop = FALSE]
        reordered_p <- p_matrix[reorder_idx, reorder_idx, drop = FALSE]

        n_clusters <- payload$n_clusters
        distance_threshold <- payload$distance_threshold
        if (!is.null(n_clusters) && is.finite(as.numeric(n_clusters))) {
          k <- max(1L, min(length(variables), as.integer(n_clusters)))
          cluster_labels <- cutree(hc, k = k)
        } else if (!is.null(distance_threshold) && is.finite(as.numeric(distance_threshold)) && as.numeric(distance_threshold) > 0) {
          cluster_labels <- cutree(hc, h = as.numeric(distance_threshold))
        } else {
          k_auto <- min(3L, length(variables))
          cluster_labels <- cutree(hc, k = max(1L, as.integer(k_auto)))
        }

        reordered_labels <- as.integer(cluster_labels[reorder_idx])
        cluster_assignments <- as.list(as.integer(cluster_labels))
        names(cluster_assignments) <- variables

        cluster_ids <- sort(unique(reordered_labels))
        clusters <- lapply(cluster_ids, function(cid) {
          members <- reordered_vars[reordered_labels == cid]
          list(
            id = as.integer(cid),
            variables = as.list(as.character(members)),
            n_variables = as.integer(length(members))
          )
        })

        heatmap_data <- list()
        idx <- 1
        for (i in seq_along(reordered_vars)) {
          for (j in seq_along(reordered_vars)) {
            p_raw <- reordered_p[i, j]
            p_val <- ifelse(is.na(p_raw), NULL, as.numeric(p_raw))
            heatmap_data[[idx]] <- list(
              row = as.integer(i - 1),
              col = as.integer(j - 1),
              row_var = as.character(reordered_vars[i]),
              col_var = as.character(reordered_vars[j]),
              r = as.numeric(reordered_corr[i, j]),
              p = p_val,
              significant = ifelse(is.null(p_val), NULL, p_val < alpha)
            )
            idx <- idx + 1
          }
        }

        pvals <- c()
        corr_vals <- c()
        if (length(reordered_vars) >= 2) {
          for (i in seq_len(length(reordered_vars) - 1)) {
            for (j in (i + 1):length(reordered_vars)) {
              p <- reordered_p[i, j]
              if (is.finite(p)) {
                pvals <- c(pvals, as.numeric(p))
              }
              rv <- reordered_corr[i, j]
              if (is.finite(rv)) {
                corr_vals <- c(corr_vals, abs(as.numeric(rv)))
              }
            }
          }
        }

        if (length(pvals) > 0) {
          result$p_value <- min(pvals)
        }
        if (length(corr_vals) > 0) {
          result$stat_value <- max(corr_vals)
        }
        if (!is.null(result$p_value)) {
          result$significant <- as.logical(result$p_value < alpha)
        }

        result$linkage <- linkage_raw
        result$n_observations <- as.integer(nrow(df))
        result$n_variables <- as.integer(length(variables))
        result$n_clusters <- as.integer(length(unique(as.integer(cluster_labels))))
        result$correlation_matrix <- list(
          variables = as.list(as.character(reordered_vars)),
          values = matrix_to_rows(reordered_corr)
        )
        result$original_order <- as.list(as.character(variables))
        result$cluster_assignments <- cluster_assignments
        result$clusters <- clusters
        result$heatmap_data <- heatmap_data
        result$dendrogram <- list(
          labels = as.list(as.character(reordered_vars)),
          leaves = as.list(as.integer(reorder_idx - 1)),
          height = as.list(as.numeric(hc$height))
        )
      }
    }
  } else if (method_id == "mixed_effects") {
    df <- safe_complete(c(col_a, payload$time_col, payload$group_col, payload$subject_col))
    group_col <- payload$group_col
    time_col <- payload$time_col
    subject_col <- payload$subject_col
    if (!is.null(group_col) && !is.null(time_col) && !is.null(subject_col)) {
      formula <- as.formula(paste(col_a, "~", group_col, "*", time_col, "+ (1|", subject_col, ")"))
      fit <- lmerTest::lmer(formula, data = df)
      a <- anova(fit)
      if (!is.null(a$`Pr(>F)`)) {
        pvals <- a$`Pr(>F)`
        if (length(pvals) > 0) {
          result$p_value <- min(pvals, na.rm = TRUE)
          result$stat_value <- max(a$`F value`, na.rm = TRUE)
        }
      }
    }
  } else if (method_id == "rm_anova") {
    outcome_cols <- payload$outcome_cols
    subject_col <- payload$subject_col
    if (!is.null(outcome_cols) && length(outcome_cols) >= 2 && !is.null(subject_col)) {
      long <- data.frame()
      for (i in seq_along(outcome_cols)) {
        c <- outcome_cols[i]
        if (!c %in% names(data)) next
        tmp <- data.frame(
          subject = data[[subject_col]],
          time = as.factor(i),
          value = data[[c]]
        )
        long <- rbind(long, tmp)
      }
      long <- long[complete.cases(long), ]
      fit <- aov(value ~ time + Error(subject/time), data = long)
      s <- summary(fit)
      if (length(s) >= 2 && length(s[[2]]) >= 1) {
        pval <- s[[2]][[1]]$`Pr(>F)`[1]
        fval <- s[[2]][[1]]$`F value`[1]
        result$p_value <- unname(pval)
        result$stat_value <- unname(fval)
      }
    }
  } else if (method_id == "friedman") {
    # Preferred path: wide repeated-measures layout, same as python handler.
    outcome_cols <- payload$outcome_cols
    if (!is.null(outcome_cols) && length(outcome_cols) >= 3) {
      cols <- outcome_cols[outcome_cols %in% names(data)]
      if (length(cols) >= 3) {
        wide <- data[, cols, drop = FALSE]
        wide <- wide[complete.cases(wide), , drop = FALSE]
        if (nrow(wide) >= 3) {
          ft <- friedman.test(as.matrix(wide))
          result$p_value <- unname(ft$p.value)
          result$stat_value <- unname(ft$statistic)
        }
      }
    }

    # Backward-compatible path: long format with explicit time/subject.
    if (is.null(result$p_value) || is.na(result$p_value)) {
      df <- safe_complete(c(col_a, payload$time_col, payload$subject_col))
      time_col <- payload$time_col
      subject_col <- payload$subject_col
      if (!is.null(time_col) && !is.null(subject_col)) {
        ft <- friedman.test(df[[col_a]] ~ df[[time_col]] | df[[subject_col]])
        result$p_value <- unname(ft$p.value)
        result$stat_value <- unname(ft$statistic)
      }
    }
  }
}, silent = TRUE)

write_json(result, output_path, auto_unbox = TRUE, null = "null")
