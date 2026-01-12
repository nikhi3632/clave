/**
 * Custom Next.js server with graceful shutdown support.
 *
 * This server handles SIGTERM and SIGINT signals to gracefully
 * shut down the application, allowing in-flight requests to complete.
 *
 * Usage:
 *   NODE_ENV=production node server.mjs
 *
 * For development, use `npm run dev` instead.
 */

import { createServer } from "http";
import { parse } from "url";
import next from "next";

const dev = process.env.NODE_ENV !== "production";
const hostname = process.env.HOSTNAME || "localhost";
const port = parseInt(process.env.PORT || "3000", 10);

// Track server state
let isShuttingDown = false;
let activeConnections = new Set();

// Initialize Next.js app
const app = next({ dev, hostname, port });
const handle = app.getRequestHandler();

/**
 * Graceful shutdown handler
 */
async function gracefulShutdown(signal) {
  if (isShuttingDown) {
    console.log(`[${signal}] Shutdown already in progress...`);
    return;
  }

  isShuttingDown = true;
  console.log(`\n[${signal}] Graceful shutdown initiated...`);

  // Stop accepting new connections
  server.close(() => {
    console.log("[shutdown] HTTP server closed");
  });

  // Set a hard timeout for shutdown
  const forceShutdownTimeout = setTimeout(() => {
    console.error("[shutdown] Force shutdown after timeout");
    process.exit(1);
  }, 30000); // 30 second timeout

  // Wait for active connections to complete
  if (activeConnections.size > 0) {
    console.log(`[shutdown] Waiting for ${activeConnections.size} active connections...`);

    // Give connections time to complete gracefully
    await new Promise((resolve) => {
      const checkInterval = setInterval(() => {
        if (activeConnections.size === 0) {
          clearInterval(checkInterval);
          resolve();
        }
      }, 100);

      // Don't wait forever for connections
      setTimeout(() => {
        clearInterval(checkInterval);
        if (activeConnections.size > 0) {
          console.log(`[shutdown] Closing ${activeConnections.size} remaining connections`);
          activeConnections.forEach((socket) => {
            socket.destroy();
          });
        }
        resolve();
      }, 10000); // 10 second grace period for connections
    });
  }

  // Clean up Next.js
  try {
    await app.close();
    console.log("[shutdown] Next.js app closed");
  } catch (error) {
    console.error("[shutdown] Error closing Next.js app:", error);
  }

  clearTimeout(forceShutdownTimeout);
  console.log("[shutdown] Graceful shutdown complete");
  process.exit(0);
}

// Create HTTP server
let server;

app.prepare().then(() => {
  server = createServer(async (req, res) => {
    // Reject new requests during shutdown
    if (isShuttingDown) {
      res.writeHead(503, {
        "Content-Type": "application/json",
        "Connection": "close",
        "Retry-After": "30",
      });
      res.end(JSON.stringify({ error: "Server is shutting down" }));
      return;
    }

    try {
      const parsedUrl = parse(req.url, true);
      await handle(req, res, parsedUrl);
    } catch (err) {
      console.error("Error handling request:", err);
      res.statusCode = 500;
      res.end("Internal Server Error");
    }
  });

  // Track connections for graceful shutdown
  server.on("connection", (socket) => {
    activeConnections.add(socket);

    socket.on("close", () => {
      activeConnections.delete(socket);
    });
  });

  // Handle server errors
  server.on("error", (err) => {
    if (err.code === "EADDRINUSE") {
      console.error(`Port ${port} is already in use`);
      process.exit(1);
    }
    console.error("Server error:", err);
  });

  // Register signal handlers
  process.on("SIGTERM", () => gracefulShutdown("SIGTERM"));
  process.on("SIGINT", () => gracefulShutdown("SIGINT"));

  // Handle uncaught exceptions
  process.on("uncaughtException", (err) => {
    console.error("Uncaught exception:", err);
    gracefulShutdown("uncaughtException");
  });

  // Handle unhandled promise rejections
  process.on("unhandledRejection", (reason, promise) => {
    console.error("Unhandled rejection at:", promise, "reason:", reason);
  });

  // Start server
  server.listen(port, hostname, () => {
    console.log(`> Server ready on http://${hostname}:${port}`);
    console.log(`> Environment: ${dev ? "development" : "production"}`);
    console.log("> Press Ctrl+C to stop");
  });
});
