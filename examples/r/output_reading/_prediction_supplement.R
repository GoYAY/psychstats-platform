# Prediction-only appendix: keep the original result.json intact.
reporting_fit <- if (CASE_ID == "selection") selected else fit
frame <- model.frame(reporting_fit)
predictors <- all.vars(delete.response(terms(reporting_fit)))
x_name <- if (CASE_ID == "logistic") "sleep_hours" else if (CASE_ID == "ancova") "pre_score" else if ("stress" %in% predictors) "stress" else predictors[1]
stopifnot(x_name %in% names(frame), is.numeric(frame[[x_name]]))
values <- seq(min(frame[[x_name]]), max(frame[[x_name]]), length.out = 81)
fixed <- list()
for (name in setdiff(predictors, x_name)) {
  if (is.numeric(frame[[name]])) fixed[[name]] <- mean(frame[[name]])
}
groups <- if (CASE_ID == "ancova") levels(frame$condition) else "条件预测"
grid <- do.call(rbind, lapply(groups, function(group) {
  newdata <- data.frame(values); names(newdata) <- x_name
  for (name in names(fixed)) newdata[[name]] <- fixed[[name]]
  if (CASE_ID == "ancova") newdata$condition <- factor(group, levels = levels(frame$condition))
  if (inherits(reporting_fit, "glm")) {
    predicted <- predict(reporting_fit, newdata, type = "link", se.fit = TRUE)
    estimate <- plogis(predicted$fit)
    lower <- plogis(predicted$fit - qnorm(0.975) * predicted$se.fit)
    upper <- plogis(predicted$fit + qnorm(0.975) * predicted$se.fit)
  } else {
    predicted <- predict(reporting_fit, newdata, interval = "confidence", level = 0.95)
    estimate <- predicted[, "fit"]; lower <- predicted[, "lwr"]; upper <- predicted[, "upr"]
  }
  data.frame(group = group, x = values, estimate = estimate, ci_lower = lower, ci_upper = upper)
}))
display <- c(stress = "压力分数", pre_score = "前测成绩", sleep_hours = "睡眠时长（小时）",
             social_support = "社会支持分数", age = "年龄（岁）")
spec <- list(x = x_name, x_label = unname(display[x_name]),
             y_label = if (CASE_ID == "logistic") "筛查阳性预测概率" else if (CASE_ID == "ancova") "预测后测成绩" else "预测幸福感分数",
             scale = if (CASE_ID == "logistic") "probability" else "mean", fixed = fixed,
             confidence = if (CASE_ID == "logistic") "线性预测子上的 Wald 95% 区间，经逆 logit 转为概率" else "条件均值的 t 分布 95% 置信区间",
             n = nobs(reporting_fit))
observations <- if (CASE_ID == "linear-simple") data.frame(x = frame[[x_name]], y = model.response(frame)) else list()
jsonlite::write_json(list(predictions = grid, specification = spec, observations = observations,
                         coefficients = as.list(coef(reporting_fit))), "prediction-result.json",
                    auto_unbox = TRUE, digits = 16, pretty = TRUE, na = "null")
