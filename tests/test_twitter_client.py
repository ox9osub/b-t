from unittest.mock import MagicMock, patch
import pytest
from src.lib.twitter_client import TwitterClient, DuplicateTweetError


def make_client(mock_api):
    """Helper: TwitterClient with a mocked tweepy.Client injected."""
    c = TwitterClient(
        api_key="k", api_secret="s",
        access_token="t", access_token_secret="ts",
        _client=mock_api,
    )
    return c


def test_post_tweet_success():
    mock_api = MagicMock()
    mock_api.create_tweet.return_value.data = {"id": "1234567890"}
    c = make_client(mock_api)
    tweet_id = c.post_tweet("hello")
    assert tweet_id == "1234567890"
    mock_api.create_tweet.assert_called_once_with(text="hello")


def test_post_thread_chains_replies():
    mock_api = MagicMock()
    # Each call returns a different ID
    mock_api.create_tweet.side_effect = [
        MagicMock(data={"id": "111"}),
        MagicMock(data={"id": "222"}),
        MagicMock(data={"id": "333"}),
    ]
    c = make_client(mock_api)
    ids = c.post_thread(["a", "b", "c"])
    assert ids == ["111", "222", "333"]
    # Verify reply chain
    calls = mock_api.create_tweet.call_args_list
    assert calls[0].kwargs == {"text": "a"}
    assert calls[1].kwargs == {"text": "b", "in_reply_to_tweet_id": "111"}
    assert calls[2].kwargs == {"text": "c", "in_reply_to_tweet_id": "222"}


def test_duplicate_tweet_raises_specific_error():
    import tweepy
    mock_api = MagicMock()
    # Simulate tweepy raising Forbidden with duplicate-content code
    err = tweepy.errors.Forbidden(MagicMock(status_code=403, text="duplicate content"))
    err.api_codes = [187]
    mock_api.create_tweet.side_effect = err
    c = make_client(mock_api)
    with pytest.raises(DuplicateTweetError):
        c.post_tweet("hello")
