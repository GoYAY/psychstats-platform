# Deterministic teaching data, not observations from a real study.
control <- c(2, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 19, 20, 23, 27)
training <- c(5, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 22, 23, 26, 30)
fit <- wilcox.test(training, control, exact = FALSE, correct = TRUE,
                   conf.int = TRUE, conf.level = 0.95)
print(fit)
prob <- mean(outer(training, control, ">")) + 0.5 * mean(outer(training, control, "=="))
print(c(n_training = length(training), n_control = length(control),
        median_training = median(training), median_control = median(control),
        superiority_training = prob))
before <- 40:59
change <- c(-6, -4, -2, -1, 0, 1, 2, 3, 4, 5, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16)
after <- before + change
paired_fit <- wilcox.test(after, before, paired = TRUE, exact = FALSE,
                          correct = TRUE, conf.int = TRUE, conf.level = 0.95)
print(paired_fit)
print(c(n_pairs = length(change), n_nonzero = sum(change != 0),
        median_before = median(before), median_after = median(after),
        median_change = median(change)))
stopifnot(as.numeric(fit$statistic) == 160.5, sum(change != 0) == 19,
          as.numeric(paired_fit$statistic) == 168)
