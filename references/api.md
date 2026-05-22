# Jike API Reference

Base URL: `https://api.ruguoapp.com`

## Required Headers

All requests must include:

| Header | Value |
|--------|-------|
| `Origin` | `https://web.okjike.com` |
| `User-Agent` | Mobile Safari UA string |
| `Accept` | `application/json, text/plain, */*` |
| `DNT` | `1` |
| `Content-Type` | `application/json` (POST only) |

Authenticated requests add: `x-jike-access-token: <token>`

---

## Authentication

### Create Session

```
POST /sessions.create
```

Response:
```json
{ "uuid": "c075565c-3538-40c7-a714-a00bc3a7f6b5" }
```

### QR Code Payload Format

```
jike://page.jk/web?url=https%3A%2F%2Fwww.okjike.com%2Faccount%2Fscan%3Fuuid%3D<uuid>&displayHeader=false&displayFooter=false
```

### Poll Confirmation

```
GET /sessions.wait_for_confirmation?uuid=<uuid>
```

- `200` — Success. Body contains `access_token` and `refresh_token`
- `400` — `SESSION_IN_WRONG_STATUS`, keep polling

### Refresh Tokens

```
POST /app_auth_tokens.refresh
Header: x-jike-refresh-token: <refresh_token>
Body: {}
```

Response headers contain refreshed `x-jike-access-token` and `x-jike-refresh-token`.

---

## Feed

### Following Feed

```
POST /1.0/personalUpdate/followingUpdates
Header: x-jike-access-token: <token>
Body: { "limit": 20, "loadMoreKey": "<optional>" }
```

### Single Post Detail (alternate)

```
POST /1.0/personalUpdate/single
Body: { "id": "<postId>" }
```

Note: this endpoint is only documented here as an observed alternate detail
lookup. Current package and export code use `/1.0/originalPosts/get` for post
detail and `/1.0/userPost/listMore` for user history pagination.

---

## Posts

### Get Post

```
GET /1.0/originalPosts/get?id=<postId>
```

### Create Post

```
POST /1.0/originalPosts/create
Body: {
  "content": "Hello world",
  "pictureKeys": [],
  "topicIds": [],
  "linkInfo": {}
}
```

`pictureKeys`, `topicIds`, and `linkInfo` are optional. The packaged client
exposes them through `JikeClient.create_post(...)` and the `jike post`
`--picture-keys`, `--topic-ids`, `--link-title`, and `--link-url` flags.

### Delete Post

```
POST /1.0/originalPosts/remove
Body: { "id": "<postId>" }
```

---

## Comments

### Add Comment

```
POST /1.0/comments/add
Body: {
  "targetType": "ORIGINAL_POST",  // or "REPOST"
  "targetId": "<postId>",
  "content": "Nice post!",
  "syncToPersonalUpdates": false,
  "pictureKeys": [],
  "force": false
}
```

### Remove Comment

```
POST /1.0/comments/remove
Body: {
  "id": "<commentId>",
  "targetType": "ORIGINAL_POST"  // or "REPOST"
}
```

---

## Search

### Integrated Search

```
POST /1.0/search/integrate
Body: {
  "keyword": "AI",
  "limit": 20,
  "loadMoreKey": "<optional>"
}
```

---

## User Posts

### List User Posts (Paginated)

```
POST /1.0/userPost/listMore
Body: {
  "username": "<username>",
  "limit": 20,
  "loadMoreKey": { "lastId": "<post_id>" }  // optional, from previous response
}
```

Response:
```json
{
  "success": true,
  "data": [ { "id": "...", "type": "ORIGINAL_POST", "content": "...", "createdAt": "...", "pictures": [...], "topic": {...}, "linkInfo": {...}, "target": {...} }, ... ],
  "loadMoreKey": { "lastId": "<next_page_cursor>" }
}
```

Notes:
- Current implementation sends `limit`; the server may still apply its own page size
- `loadMoreKey` is `null` or absent when no more posts exist
- `loadMoreKey` is an object `{"lastId": "..."}`, not a string
- `type` is `ORIGINAL_POST` or `REPOST`
- `target` field is present only for reposts, containing the original post
- `pictures` is an array of objects with `picUrl`, `middlePicUrl`, `thumbnailUrl`

---

## Users

### User Profile

```
GET /1.0/users/profile?username=<id_or_username>
```

### Followers

```
POST /1.0/userRelation/getFollowerList
Body: { "userId": "<userId>", "loadMoreKey": "<optional>" }
```

### Following

```
POST /1.0/userRelation/getFollowingList
Body: { "userId": "<userId>", "loadMoreKey": "<optional>" }
```

---

## Notifications

### Unread Count

```
GET /1.0/notifications/unread
```

### Notification List

```
POST /1.0/notifications/list
Body: { "loadMoreKey": "<optional>" }
```

---

## Error Handling

| Status | Meaning | Action |
|--------|---------|--------|
| `200` | Success | Process response |
| `400` | Bad request / polling | Retry or check params |
| `401` | Token expired | Refresh via `app_auth_tokens.refresh`, retry once |
| `403` | Forbidden | Check permissions |
| `404` | Not found | Verify resource ID |
