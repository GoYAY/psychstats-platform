d <- read.csv("your_data.csv")
stopifnot(is.numeric(d$x),is.numeric(d$y))
plot(d$x,d$y); cor.test(d$x,d$y,method="pearson")
# Inspect shape, outliers, and independence before interpreting r.
