set.seed(42)
sample_means <- replicate(2000,mean(sample(your_population_vector,40,replace=TRUE)))
hist(sample_means); sd(sample_means)
# Replace your_population_vector with a numeric vector from your data.
