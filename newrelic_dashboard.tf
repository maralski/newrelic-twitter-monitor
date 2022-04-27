
resource "newrelic_one_dashboard" "twitter_monitor" {
  name = "Twitter Monitor"

  page {
    name = "Overview"

    widget_markdown {
      title = ""
      row = 1
      column = 1
      height = 2
      width = 4
      text = <<EOT
## Welcome to Twitter Monitor
This dashboard displays the tweets tracked by nrtweetmon in real-time. The 
sentiment scores range from 0 (negative) to 1 (positive) with 0.5 representing a  neutral score.
Each rule represents the tag associated with a tweetmon filter.

The New Relic Log viewer can also be used to view and analyse tweets captured by nrtweetmon. Simply filter for `provider = nrtweetmon`.
EOT
    }

    widget_line {
      title = "Sentiment Score (p90)"
      row = 1
      column = 5
      height = 4
      width = 4

      nrql_query {
        query = <<EOT
FROM Log SELECT percentile(score, 90) WHERE provider = 'nrtwittermon' FACET matching_rule TIMESERIES
EOT
      }
    }

    widget_stacked_bar {
      title = "Number of Tweets by Rule"
      row = 1
      column = 9
      height = 2
      width = 4

      nrql_query {
        query = <<EOT
FROM Log SELECT count(*) WHERE provider = 'nrtwittermon' TIMESERIES FACET matching_rule
EOT
      }
    }

    widget_pie {
      title = "Tweets by Rule"
      row = 3
      column = 1
      height = 2
      width = 4

      nrql_query {
        query = <<EOT
FROM Log SELECT count(*) AS 'Tweets' WHERE provider = 'nrtwittermon' FACET matching_rule 
EOT
      }
    }

    widget_stacked_bar {
      title = "Top 5 Twitter Users"
      row = 3
      column = 9
      height = 2
      width = 4

      nrql_query {
        query = <<EOT
FROM Log SELECT count(*) WHERE provider = 'nrtwittermon' FACET username TIMESERIES LIMIT 5
EOT
      }
    }

    widget_table {
      title = "Latest 10 Tweets"
      row = 5
      column = 1
      height = 5
      width = 12

      nrql_query {
        query = <<EOT
FROM Log SELECT url, sentiment, matching_rule AS 'rule', message WHERE provider = 'nrtwittermon' LIMIT 10
EOT
      }
    }
  }

  page {
    name = "Popular Tweets"

    widget_table {
      title = "Most Retweets"
      row = 1
      column = 1
      height = 3
      width = 12

      nrql_query {
        query = <<EOT
FROM Log SELECT max(retweet_count) AS 'Retweets', latest(url), latest(username), latest(sentiment), latest(message) WHERE retweet_count > 0 AND provider = 'nrtwittermon' FACET matching_rule
EOT
      }
    }

    widget_table {
      title = "Most Liked"
      row = 4
      column = 1
      height = 3
      width = 12

      nrql_query {
        query = <<EOT
FROM Log SELECT max(like_count) AS 'Liked', latest(url), latest(username), latest(sentiment), latest(message) WHERE like_count > 0 AND provider = 'nrtwittermon' FACET matching_rule
EOT
      }
    }

    widget_table {
      title = "Most Replied"
      row = 7
      column = 1
      height = 3
      width = 12

      nrql_query {
        query = <<EOT
FROM Log SELECT max(reply_count) AS 'Replied', latest(url), latest(username), latest(sentiment), latest(message) WHERE reply_count > 0 AND provider = 'nrtwittermon' FACET matching_rule
EOT
      }
    }
  }
}
