#!/usr/bin/env python3
"""Streamlit page for viewing documents securely."""

import os
import sys
import base64
from pathlib import Path
from urllib.parse import unquote

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st  # pyright: ignore[reportMissingImports]
import streamlit.components.v1 as components

# Page configuration
st.set_page_config(
    page_title="View Document",
    page_icon="📄",
    layout="wide"
)


def validate_file_path(file_path: str, documents_folder: str) -> tuple[bool, str]:
    """
    Validate that the file path is safe and within the documents folder.
    
    Args:
        file_path: Relative file path from query parameter
        documents_folder: Path to documents folder
        
    Returns:
        Tuple of (is_valid, resolved_path)
    """
    # Decode URL-encoded path
    file_path = unquote(file_path)
    
    # Resolve documents folder to absolute path
    docs_abs = os.path.abspath(documents_folder)
    
    # Resolve file path
    if os.path.isabs(file_path):
        resolved_path = os.path.abspath(file_path)
    else:
        resolved_path = os.path.abspath(os.path.join(documents_folder, file_path))
    
    # Normalize paths to handle .. and . components
    resolved_path = os.path.normpath(resolved_path)
    docs_abs = os.path.normpath(docs_abs)
    
    # Security check: ensure file is within documents folder
    try:
        # Check if resolved path starts with documents folder
        if not resolved_path.startswith(docs_abs):
            return False, ""
        
        # Check if file exists
        if not os.path.exists(resolved_path):
            return False, ""
        
        # Check if it's a file (not a directory)
        if not os.path.isfile(resolved_path):
            return False, ""
        
        # Check file extension (only allow safe types)
        allowed_extensions = {'.pdf', '.txt', '.md', '.markdown', '.html', '.htm'}
        file_ext = os.path.splitext(resolved_path)[1].lower()
        if file_ext not in allowed_extensions:
            return False, ""
        
        return True, resolved_path
    
    except Exception:
        return False, ""


def main():
    """Main function for document viewer page."""
    # Get file parameter from session state (set by navigation button) or query string
    file_param = None
    
    # First check session state (set when navigating from citation button)
    if 'view_document_file' in st.session_state:
        file_param = st.session_state['view_document_file']
        # Clear it after use so it doesn't persist
        del st.session_state['view_document_file']
    
    # Fall back to query parameters (for direct URL access)
    if not file_param:
        try:
            if hasattr(st, 'query_params'):
                file_param = st.query_params.get('file', None)
            else:
                query_params = st.experimental_get_query_params()
                file_param = query_params.get('file', [None])[0] if query_params.get('file') else None
        except Exception:
            file_param = None
    
    if not file_param:
        st.error("No file specified. Please provide a file parameter.")
        st.info("Navigate from a citation link or use: /view_document?file=document.pdf")
        if st.button("← Back to Chat"):
            # Navigate back to main app - use the main app filename without extension
            st.switch_page("streamlit_app")
        return
    
    # Documents folder path
    documents_folder = os.path.join(project_root, "documents")
    
    # Validate file path
    is_valid, resolved_path = validate_file_path(file_param, documents_folder)
    
    if not is_valid:
        st.error("Invalid file path or file not found.")
        st.info(f"Requested file: {file_param}")
        st.info(f"Documents folder: {documents_folder}")
        st.info(f"Project root: {project_root}")
        return
    
    # Get file name for display
    file_name = os.path.basename(resolved_path)
    file_ext = os.path.splitext(file_name)[1].lower()
    
    # Read file
    try:
        with open(resolved_path, 'rb') as f:
            file_bytes = f.read()
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return
    
    # Display file
    st.title(f"📄 {file_name}")
    
    # Add back button
    if st.button("← Back to Chat"):
        # Navigate back to main app - use the main app filename without extension
        st.switch_page("streamlit_app")
    
    st.markdown("---")
    
    # Handle different file types
    if file_ext == '.pdf':
        # Convert PDF to base64 for embedding
        base64_pdf = base64.b64encode(file_bytes).decode('utf-8')
        
        # Action buttons
        pdf_data_uri = f"data:application/pdf;base64,{base64_pdf}"
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Create a proper HTML link that opens PDF in new tab
            open_pdf_html = f"""
            <div style="text-align: center;">
                <a href="{pdf_data_uri}" target="_blank" 
                   style="display: inline-block; background-color: #1E3A8A; color: white; 
                          padding: 10px 20px; border-radius: 5px; text-decoration: none; 
                          font-weight: bold; width: 100%; text-align: center;">
                    📄 Open PDF in New Tab
                </a>
            </div>
            """
            components.html(open_pdf_html, height=50)
        
        with col2:
            st.download_button(
                label="📥 Download PDF",
                data=file_bytes,
                file_name=file_name,
                mime_type="application/pdf",
                use_container_width=True
            )
        
        st.markdown("---")
        
        # Use Streamlit's HTML component for inline PDF display
        # Create HTML with iframe for PDF display
        # Note: Some browsers block data URIs in iframes, so this may not work in all browsers
        pdf_html = f"""
        <div style="width: 100%; height: 800px; border: 1px solid #ccc; background: #f0f0f0;">
            <iframe 
                src="data:application/pdf;base64,{base64_pdf}#toolbar=1&navpanes=1&scrollbar=1" 
                width="100%" 
                height="100%" 
                frameborder="0"
                style="border: none;">
            </iframe>
            <noscript>
                <p style="padding: 20px; text-align: center;">
                    JavaScript is required to display PDFs inline. 
                    <a href="data:application/pdf;base64,{base64_pdf}" download="{file_name}">Download the PDF</a> instead.
                </p>
            </noscript>
        </div>
        """
        
        components.html(pdf_html, height=800)
        
        st.info("💡 If the PDF doesn't display above, use the 'Open in New Tab' button for the best viewing experience.")
        
        # Debug info (can be removed later)
        with st.expander("Debug Info", expanded=False):
            st.write(f"File size: {len(file_bytes)} bytes")
            st.write(f"File path: {resolved_path}")
            st.write(f"Base64 length: {len(base64_pdf)} characters")
            st.write(f"File exists: {os.path.exists(resolved_path)}")
            st.write(f"File readable: {os.access(resolved_path, os.R_OK)}")
    
    elif file_ext in {'.txt', '.md', '.markdown'}:
        # Display text files directly
        try:
            text_content = file_bytes.decode('utf-8')
            st.markdown(text_content)
        except UnicodeDecodeError:
            st.error("File encoding not supported. Please download the file.")
            st.download_button(
                label="📥 Download File",
                data=file_bytes,
                file_name=file_name,
                mime_type="text/plain"
            )
    
    elif file_ext in {'.html', '.htm'}:
        # Display HTML files
        html_content = file_bytes.decode('utf-8')
        st.markdown(html_content, unsafe_allow_html=True)
        
        st.download_button(
            label="📥 Download HTML",
            data=file_bytes,
            file_name=file_name,
            mime_type="text/html"
        )
    
    else:
        # Fallback: download button only
        st.info(f"Preview not available for {file_ext} files.")
        st.download_button(
            label="📥 Download File",
            data=file_bytes,
            file_name=file_name
        )


if __name__ == "__main__":
    main()

