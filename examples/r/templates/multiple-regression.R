d <- read.csv("your_data.csv")
stopifnot(all(c("outcome","predictor1","predictor2") %in% names(d)))
fit <- lm(outcome ~ predictor1 + predictor2,data=d)
summary(fit); par(mfrow=c(2,2)); plot(fit)
# Check design, influential points, and collinearity before reporting.
