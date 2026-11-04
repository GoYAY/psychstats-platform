source("_common.R")
d <- read.csv("cross_sectional_survey.csv")
fit <- lm(well_being~stress+social_support+age,d)
X <- model.matrix(fit); h <- hatvalues(fit); e <- resid(fit); bread <- solve(crossprod(X))
meat <- crossprod(X, X*as.numeric(e^2/(1-h)^2)); hc3 <- bread%*%meat%*%bread
se <- sqrt(hc3["stress","stress"]); beta <- unname(coef(fit)["stress"]); ci <- beta+c(-1,1)*qnorm(0.975)*se
cook <- cooks.distance(fit); target <- which.max(cook)
sensitivity <- lm(well_being~stress+social_support+age,d[-target,])
print(summary(fit)); print(c(max_Cook=max(cook),row=target,HC3_SE=se)); print(summary(sensitivity))
finish(c(beta=beta,hc3_se=se,ci_lower=ci[1],ci_upper=ci[2],max_cook=max(cook),sensitivity_beta=unname(coef(sensitivity)["stress"])),list(influential=data.frame(row=order(cook,decreasing=TRUE)[1:5],cook=sort(cook,decreasing=TRUE)[1:5])))

