d <- read.csv("your_data.csv")
stopifnot(is.numeric(d$score))
d$z_score <- as.numeric(scale(d$score))
summary(d$z_score)
