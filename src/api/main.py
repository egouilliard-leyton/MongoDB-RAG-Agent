"""FastAPI application main file."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Initialize logging BEFORE importing other modules
from src.api.logging_config import setup_logging
setup_logging()

from src.api.routes import sessions, qa_pairs, questions, export, admin
from src.api.middleware import error_handler_middleware, request_logging_middleware
from src.services.background_tasks import BackgroundTaskScheduler
from src.settings import load_settings

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: BackgroundTaskScheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    global scheduler
    
    # Startup
    try:
        settings = load_settings()
        scheduler = BackgroundTaskScheduler(settings)
        await scheduler.start()
        logger.info("Application started, background tasks initialized")
    except Exception as e:
        logger.exception(f"Error starting background tasks: {e}")
    
    yield
    
    # Shutdown
    if scheduler:
        try:
            await scheduler.stop()
            logger.info("Application shutting down, background tasks stopped")
        except Exception as e:
            logger.exception(f"Error stopping background tasks: {e}")


# Create FastAPI app
app = FastAPI(
    title="MongoDB RAG Q&A API",
    description="REST API for Q&A system with MongoDB RAG backend",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware (before error handler)
app.middleware("http")(request_logging_middleware)

# Add error handling middleware (must be after CORS and request logging)
app.middleware("http")(error_handler_middleware)

# Include routers
app.include_router(sessions.router)
app.include_router(qa_pairs.router)
app.include_router(questions.router)
app.include_router(export.router)
app.include_router(admin.router)


@app.get("/health")
async def health_check():
    """Health check endpoint with dependency checks."""
    from src.dependencies import AgentDependencies
    
    health_status = {
        "status": "healthy",
        "service": "qa-api",
        "readiness": "ready"
    }
    
    # Add background task status if scheduler is available
    if scheduler:
        bg_status = scheduler.get_status()
        health_status["background_tasks"] = {
            "enabled": bg_status["enabled"],
            "running": bg_status["running"],
            "last_execution": bg_status["last_execution_time"],
            "next_execution": bg_status["next_execution_time"]
        }
    else:
        health_status["background_tasks"] = {
            "enabled": False,
            "running": False,
            "message": "Scheduler not initialized"
        }
    
    # Check MongoDB and document dependencies
    dependencies_status = {
        "mongodb": {"status": "connected"},
        "documents": {"status": "unknown", "count": 0},
        "chunks": {"status": "unknown", "count": 0},
        "vector_index": {"status": "unknown"}
    }
    
    try:
        settings = load_settings()
        agent_deps = AgentDependencies()
        await agent_deps.initialize()
        
        try:
            # Check document count
            doc_count = await agent_deps.db[settings.mongodb_collection_documents].count_documents({})
            dependencies_status["documents"]["count"] = doc_count
            dependencies_status["documents"]["status"] = "available" if doc_count > 0 else "empty"
            
            # Check chunk count
            chunk_count = await agent_deps.db[settings.mongodb_collection_chunks].count_documents({})
            dependencies_status["chunks"]["count"] = chunk_count
            dependencies_status["chunks"]["status"] = "available" if chunk_count > 0 else "empty"
            
            # Check for embeddings (sample)
            if chunk_count > 0:
                sample_chunk = await agent_deps.db[settings.mongodb_collection_chunks].find_one({})
                if sample_chunk and sample_chunk.get("embedding"):
                    dependencies_status["chunks"]["embeddings"] = "present"
                else:
                    dependencies_status["chunks"]["embeddings"] = "missing"
            
            # Check for vector index
            try:
                indexes = []
                async for idx in agent_deps.db[settings.mongodb_collection_chunks].list_indexes():
                    indexes.append(idx)
                
                vector_index_name = settings.mongodb_vector_index
                index_names = [idx.get("name", "") for idx in indexes]
                has_vector_index = any(idx.get("type") == "vectorSearch" for idx in indexes)
                
                if vector_index_name in index_names or has_vector_index:
                    dependencies_status["vector_index"]["status"] = "available"
                else:
                    dependencies_status["vector_index"]["status"] = "missing"
                    dependencies_status["vector_index"]["message"] = f"Vector index '{vector_index_name}' not found. Create in Atlas UI."
            except Exception as idx_error:
                dependencies_status["vector_index"]["status"] = "unknown"
                dependencies_status["vector_index"]["error"] = str(idx_error)
            
            # Determine overall readiness
            if doc_count == 0 or chunk_count == 0:
                health_status["readiness"] = "not_ready"
                health_status["status"] = "degraded"
            elif dependencies_status["chunks"].get("embeddings") == "missing":
                health_status["readiness"] = "not_ready"
                health_status["status"] = "degraded"
            elif dependencies_status["vector_index"]["status"] == "missing":
                health_status["readiness"] = "degraded"
                health_status["status"] = "degraded"
            else:
                health_status["readiness"] = "ready"
            
        finally:
            await agent_deps.cleanup()
    
    except Exception as e:
        logger.exception(f"Error checking dependencies: {e}")
        dependencies_status["mongodb"]["status"] = "error"
        dependencies_status["mongodb"]["error"] = str(e)
        health_status["readiness"] = "not_ready"
        health_status["status"] = "unhealthy"
    
    health_status["dependencies"] = dependencies_status
    
    return health_status


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "MongoDB RAG Q&A API",
        "version": "1.0.0",
        "docs": "/docs"
    }

