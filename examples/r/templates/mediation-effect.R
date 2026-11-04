d <- read.csv("your_data.csv")
stopifnot(all(c("x","m","y") %in% names(d)))
d <- na.omit(d[c("x","m","y")]); set.seed(42)
indirect <- function(data) coef(lm(m ~ x,data=data))["x"] * coef(lm(y ~ x + m,data=data))["m"]
estimate <- indirect(d)
boot <- replicate(2000,indirect(d[sample.int(nrow(d),replace=TRUE),]))
c(estimate=estimate,quantile(boot,c(.025,.975)))
# The bootstrap interval does not establish causality by itself.
