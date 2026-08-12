# http-server

An HTTP/1.1 server written from scratch in Python on raw sockets. No framework,
no `http.server`, no dependencies. The point isn't to end up with a web server.
The point is to understand what one actually does.

I started this because I used HTTP every day without being able to explain how a
connection stays open between requests, why a request needs a `Host` header, or
what happens to the bytes that arrive after the blank line. The fastest way to
find out was to write a server badly and then keep fixing it until it stopped
being wrong.

## What it will do when it's finished

The target client is a real browser loading a real page with several assets on
it. A browser is a client I didn't write, it follows the spec more closely than I
do, and it fails visibly in the network tab instead of quietly. The bar is
availability rather than correctness alone: nothing one client does may degrade
service for another.

Concretely, the finished server:

* **Holds connections open.** Keep-alive across requests, `Connection: close`
  honored, HTTP/1.0 clients handled with 1.0's persistence rules and unsupported
  versions rejected with 505.
* **Frames messages correctly.** Bodies read via `Content-Length`, chunked
  request bodies decoded, chunked responses when the length isn't known upfront,
  `Expect: 100-continue` answered, and conflicting `Content-Length` plus
  `Transfer-Encoding` rejected rather than guessed at, because that guess is
  request smuggling.
* **Serves a static site from a document root.** MIME types by extension, index
  files, no accidental directory listings, large files streamed instead of
  buffered into memory, and path traversal blocked against `../`, absolute
  paths, symlinks pointing out of the root, and null bytes.
* **Saves the client bandwidth.** `Last-Modified` and `ETag` on file responses,
  conditional requests answered with 304, range requests answered with 206 so
  downloads resume and media seeks, and gzip when the client asks for it.
* **Gets the required semantics right.** `Host` mandatory, `Date` on every
  response, `HEAD` wherever `GET` works, 501 for methods it doesn't implement
  and 405 with `Allow` for ones it does, request targets percent-decoded, and
  responses that must not carry a body not carrying one.
* **Survives clients that misbehave.** Read timeouts on the idle, header, and
  body phases, hard limits on header size and body size, a cap on concurrent
  connections with behavior I chose at the cap, and no leaked sockets or file
  descriptors on any path including the error paths.
* **Can be operated.** One structured access log line per request, tracebacks in
  the error log and never in a response body, logs to stdout, a meaningful exit
  code, and the same graceful shutdown for `SIGTERM` as for Ctrl-C.

Done means all four of these hold:

1. A real browser loads a multi-asset page correctly, over reused connections,
   and gets 304s on reload.
2. A hostile-client suite (silent connect, slowloris, oversized headers,
   oversized body, abrupt disconnect mid-body) cannot degrade service for any
   other client.
3. The framing and semantics behaviors are covered by automated tests.
4. A sustained `wrk` run finishes with no file-descriptor or memory growth.

## How it gets there

| | Milestone | Covers |
|---|---|---|
| M0 | Foundations | test harness, configuration, logging, graceful shutdown, signals |
| M1 | Survive hostile and slow clients | read timeouts, header limits, concurrency, connection cap, no leaked file descriptors |
| M2 | Correct message framing | `Content-Length`, chunked encoding, keep-alive, request smuggling, duplicate headers |
| M3 | Required semantics | `Host`, `Date`, `HEAD`, 501 vs 405, percent-decoding request targets |
| M4 | Serve real content | static files, MIME types, path traversal, `ETag`, conditional requests, ranges, gzip |
| M5 | Concurrency depth | benchmark baseline, a concurrency model chosen against measurements, leak checks under load |

Roughly 45 issues, one demonstrable behavior each, numbered so they follow the
build order, with the dependencies between them recorded.
[Issue #1](https://github.com/wimthomzik/http-server/issues/1) is the charter:
the goal, the things I've explicitly ruled out and why, and what counts as
finished.

Working out that order was most of the planning. Keep-alive built before body
reading, for instance, looks like it works and then silently corrupts the next
request on any connection that carried a body.

## Where it is today

Early. It serves JSON on two routes, and that is roughly the extent of it.

```
$ python3 server.py
$ curl -s http://127.0.0.1:8000/
{"path": "/", "method": "GET"}
```

It parses a request line and headers, routes on method and path, returns 404 and
405 where they belong, and catches exceptions in route code so a bug produces a
500 instead of a dead connection.

Measured against the list above, what's missing is most of it:

* It handles one connection at a time. A client that connects and then sends
  nothing blocks every other client permanently. Chrome triggers this by
  accident on an ordinary page load, because it opens speculative connections it
  may never send a byte on.
* There are no read timeouts anywhere, so "stuck" means "stuck until I restart
  it."
* It closes the connection after every response. A second request on the same
  socket gets a connection reset.
* It never reads request bodies. Everything after the header block is discarded.
* It doesn't require `Host`, doesn't send `Date`, answers `HEAD` with 405,
  answers an unknown method with 405 where the spec wants 501, and sends 405
  without the `Allow` header that's supposed to accompany it.
* There's no cap on how many bytes a client can send before the headers end, so
  a client that never stops sending headers is a memory exhaustion attack.

## Running it

Python 3, standard library only. Developed on 3.14.

```bash
python3 server.py
```

It listens on `127.0.0.1:8000`. `curl -v` is the quickest way to see what it
sends back.

## How it's put together

Four layers, each responsible for one thing:

```
serve()      accept loop, owns the listening socket
handle()     one request/response exchange on one connection
dispatch()   maps method and path to a route function
routes       application code, returns (status, content_type, body)
```

Top to bottom that's transport, protocol, routing, application. A route function
has no idea what a socket is and never touches one.

The part I care about most is where errors get caught. Each layer only handles
what it has the vocabulary to name. `serve` owns the socket, so it deals with a
client disappearing mid-exchange. `handle` owns one exchange, so it turns a
malformed request line into a 400 and an exception in route code into a 500. My
first attempt wrapped everything in a single try/except near the top, and the
result was that every failure looked identical and none of them could be
answered correctly. Splitting the error handling along the same seams as the
layering fixed that, and it's the idea I'd keep if I threw the rest away.

Whether this structure survives concurrency and keep-alive is an open question.
`handle` currently assumes one request per connection, and both of those change
what a "layer" owns.

## What I've learned so far

**A server can pass every test I thought to write and still be unusable.**
`curl` is a polite client that sends one clean request and goes away. A browser
opens connections it may never use, sends headers I've never heard of, and
reuses sockets. The single worst bug in this codebase, one silent connection
taking the whole server offline, is invisible to every manual test I would have
thought to run.

**Framing is the actual protocol.** Parsing a request line is string
manipulation and takes an afternoon. Knowing where one message ends and the next
begins is the hard part, and it's what makes persistent connections possible.
Right now `handle` reads until the blank line and throws away the rest, and that
single decision is why keep-alive can't work here yet.

**The error path needs its own error path.** `send_response` looks up the reason
phrase in a dict of status codes. It's also what the 500 handler calls. So a
status code I forgot to add to that dict raises a `KeyError` from inside the code
whose entire job is handling exceptions. Nothing in the layering protects against
that; it needed to be found by asking what happens when the recovery path itself
fails.

**The RFCs are worth reading in the original.** Not because the prose is
enjoyable, but because they specify things no client will ever complain about.
Nothing broke when I sent 405 for an unknown method instead of 501, or left out
`Date`, or ignored `Host`. It breaks later, in a cache or a proxy, at a distance
from the cause.

## Not doing

Deliberately out of scope, so I don't get pulled sideways:

* **HTTP/2 and HTTP/3.** HTTP/2 replaces the wire format completely and browsers
  only speak it over TLS, so it drags TLS in ahead of it. It's a separate
  project, not a stretch goal for this one. HTTP/3 is a transport protocol with
  its own congestion control, which is a networking project rather than an HTTP
  one.
* **TLS.** Hand-rolling it teaches cryptography, not HTTP. If it ever shows up
  here it will use the standard library.
* **Any framework, and `http.server`.** Not using them is the whole exercise.
* **Sessions, login, templating, an ORM.** A session is a key-value store and a
  cookie. None of it is HTTP, and nginx has no concept of one.
* **Being a reverse proxy.** Forwarding requests upstream makes the program an
  HTTP client as well, which is a different role and a much larger project.
  Behaving correctly *toward* proxies is in scope.
* **Beating nginx on throughput.** Measuring matters, winning doesn't.
