d <- read.csv("your_data.csv")
stopifnot(all(c("binary_outcome","predictor") %in% names(d)))
stopifnot(all(na.omit(unique(d$binary_outcome)) %in% c(0,1)))
fit <- glm(binary_outcome ~ predictor,data=d,family=binomial())
summary(fit); exp(coef(fit)); fit$converged
