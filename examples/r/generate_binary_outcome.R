# Synthetic teaching observations, not validated screening or diagnostic data.
# Run from workspace root. All coefficients below are arbitrary teaching choices.
set.seed(20261001)
n <- 300L
sleep_hours <- round(pmin(10, pmax(3, rnorm(n, 7, 1.1))), 1)
stress <- round(pmin(80, pmax(10, rnorm(n, 45, 9))), 1)
age <- sample(18:30, n, replace=TRUE)
p <- plogis(-0.6 + 0.06*(stress-45) - 0.4*(sleep_hours-7) + 0.02*(age-24))
screen_positive <- rbinom(n, 1, p)
d <- data.frame(id=seq_len(n), sleep_hours, stress, age, screen_positive)
write.csv(d, 'examples/data/binary_outcome_teaching.csv', row.names=FALSE)
