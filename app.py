import streamlit as st
import pandas as pd
import os
from pathlib import Path
from datetime import datetime

from core.wo_processor import WOProcessor
from core.ata_catalog import ATACatalog

# Page config
st.set_page_config(
    page_title="ATA Work Order Analyzer",
    page_icon="✈️",
    layout="wide"
)

# Initialize session state
if 'processor' not in st.session_state:
    st.session_state.processor = None
if 'results' not in st.session_state:
    st.session_state.results = None

def load_catalog():
    """Load ATA Catalog"""
    catalog_path = Path("catalog/ata_catalog.json")
    if not catalog_path.exists():
        return None
    
    try:
        catalog = ATACatalog(catalog_dir="catalog")
        return catalog
    except Exception as e:
        st.error(f"❌ Error loading catalog: {str(e)}")
        return None

def show_catalog_setup_guide():
    """Show guide for setting up catalog"""
    st.warning("⚠️ Catalog not found - Please build the catalog first")
    
    with st.expander("📘 How to build the catalog", expanded=True):
        st.markdown("""
        ### Option 1: Build from SGML files
        
        If you have SGML manual files:
        
        ```bash
        python scripts/build_ata_catalog.py --tar path/to/SGML_A320.tar
        ```
        
        ### Option 2: Use sample catalog (for testing)
        
        Create a minimal catalog for testing:
        
        ```bash
        python scripts/create_sample_catalog.py
        ```
        
        ### Option 3: Manual catalog directory
        
        Or place your pre-built catalog files in:
        - `catalog/ata_catalog.json`
        - `catalog/model/tfidf_vectorizer.pkl`
        - `catalog/model/tfidf_matrix.pkl`
        """)
        
        if st.button("🔄 Refresh - Check Again"):
            st.rerun()

def main():
    st.title("✈️ ATA Work Order Analyzer")
    st.markdown("**Xác định ATA 4 ký tự từ Work Orders**")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Check catalog status
        catalog_exists = Path("catalog/ata_catalog.json").exists()
        
        if catalog_exists:
            st.success("✅ Catalog loaded")
        else:
            st.error("❌ Catalog not found")
            st.caption("Build catalog first")
        
        st.divider()
        
        # Mode selection
        mode = st.radio(
            "Processing Mode",
            ["Catalog (TF-IDF)", "RAG (Advanced)"],
            help="Catalog mode: Fast, offline | RAG mode: Deep search, requires API",
            disabled=not catalog_exists
        )
        
        # Confidence threshold
        confidence_threshold = st.slider(
            "Confidence Threshold",
            min_value=0.5,
            max_value=1.0,
            value=0.75,
            step=0.05,
            help="Minimum confidence for CONFIRM/CORRECT decisions",
            disabled=not catalog_exists
        )
        
        # Non-defect filtering
        filter_non_defect = st.checkbox(
            "Filter Non-Defect WOs",
            value=True,
            help="Remove routine maintenance, cleaning, etc.",
            disabled=not catalog_exists
        )
        
        st.divider()
        st.markdown("### 📚 Quick Guide")
        st.markdown("""
        1. Upload Excel WO file
        2. Configure settings
        3. Click 'Process'
        4. Download results
        """)
    
    # Main content
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Process", "📊 Results", "ℹ️ Help"])
    
    with tab1:
        # Check if catalog exists
        if not Path("catalog/ata_catalog.json").exists():
            show_catalog_setup_guide()
            return
        
        st.header("Upload Work Orders")
        
        uploaded_file = st.file_uploader(
            "Choose Excel file",
            type=['xlsx', 'xls'],
            help="File should contain columns: ATA, W/O Description, W/O Action, Type, A/C, Issued, Closed"
        )
        
        if uploaded_file:
            try:
                df = pd.read_excel(uploaded_file)
                st.success(f"✅ Loaded {len(df)} work orders")
                
                # Show preview
                with st.expander("📋 Preview data (first 5 rows)"):
                    st.dataframe(df.head())
                
                # Column mapping check
                required_cols = ['ATA', 'W/O Description', 'W/O Action', 'Type', 'A/C', 'Issued', 'Closed']
                missing_cols = [col for col in required_cols if col not in df.columns]
                
                if missing_cols:
                    st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
                    st.info("Required columns: ATA, W/O Description, W/O Action, Type, A/C, Issued, Closed")
                else:
                    st.success("✅ All required columns present")
                    
                    # Process button
                    if st.button("🚀 Process Work Orders", type="primary"):
                        with st.spinner("Processing... This may take a few minutes."):
                            try:
                                # Load catalog
                                catalog = load_catalog()
                                if catalog is None:
                                    st.stop()
                                
                                # Initialize processor
                                processor = WOProcessor(
                                    catalog=catalog,
                                    mode='catalog' if mode == "Catalog (TF-IDF)" else 'rag',
                                    filter_non_defect=filter_non_defect,
                                    confidence_threshold=confidence_threshold
                                )
                                
                                # Process
                                results_df = processor.process_dataframe(df)
                                st.session_state.results = results_df
                                st.session_state.processor = processor
                                
                                st.success("✅ Processing complete!")
                                st.balloons()
                                
                            except Exception as e:
                                st.error(f"❌ Error during processing: {str(e)}")
                                st.exception(e)
            
            except Exception as e:
                st.error(f"❌ Error reading file: {str(e)}")
    
    with tab2:
        st.header("Processing Results")
        
        if st.session_state.results is not None:
            results_df = st.session_state.results
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total WOs", len(results_df))
            
            with col2:
                technical_defects = results_df['Is_Technical_Defect'].sum()
                st.metric("Technical Defects", technical_defects)
            
            with col3:
                confirms = (results_df['Decision'] == 'CONFIRM').sum()
                st.metric("CONFIRM", confirms)
            
            with col4:
                reviews = (results_df['Decision'] == 'REVIEW').sum()
                st.metric("REVIEW", reviews)
            
            # Decision breakdown
            st.subheader("Decision Breakdown")
            decision_counts = results_df['Decision'].value_counts()
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.dataframe(decision_counts, use_container_width=True)
            
            with col2:
                st.bar_chart(decision_counts)
            
            # Confidence distribution
            st.subheader("Confidence Distribution")
            st.histogram_chart(results_df[results_df['Confidence'].notna()]['Confidence'])
            
            # Detailed results
            st.subheader("Detailed Results")
            
            # Filter options
            filter_col1, filter_col2 = st.columns(2)
            with filter_col1:
                decision_filter = st.multiselect(
                    "Filter by Decision",
                    options=results_df['Decision'].unique(),
                    default=results_df['Decision'].unique()
                )
            
            with filter_col2:
                defect_filter = st.selectbox(
                    "Filter by Defect Status",
                    options=["All", "Technical Defects Only", "Non-Defects Only"]
                )
            
            # Apply filters
            filtered_df = results_df[results_df['Decision'].isin(decision_filter)]
            
            if defect_filter == "Technical Defects Only":
                filtered_df = filtered_df[filtered_df['Is_Technical_Defect'] == True]
            elif defect_filter == "Non-Defects Only":
                filtered_df = filtered_df[filtered_df['Is_Technical_Defect'] == False]
            
            st.dataframe(
                filtered_df,
                use_container_width=True,
                height=400
            )
            
            # Download button
            st.download_button(
                label="📥 Download Results (Excel)",
                data=self._to_excel(results_df),
                file_name=f"WO_ATA_checked_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        else:
            st.info("👆 Upload and process work orders to see results here")
    
    with tab3:
        st.header("Help & Documentation")
        
        st.markdown("""
        ### Column Mapping
        
        | Excel Column | Internal Mapping | Description |
        |-------------|------------------|-------------|
        | ATA | ATA04_Entered | ATA entered by mechanic |
        | W/O Description | Defect_Text | Defect description |
        | W/O Action | Rectification_Text | Rectification action |
        | Type | WO_Type | WO type (Pilot/Maint/Cabin) |
        | A/C | AC_Registration | Aircraft registration |
        | Issued | Open_Date | WO open date |
        | Closed | Close_Date | WO close date |
        | ATA 04 Corrected | ATA04_Final | Final ATA (output) |
        
        ### Decision Logic
        
        - **CONFIRM**: ATA entered is correct (high confidence)
        - **CORRECT**: ATA should be changed (high confidence)
        - **REVIEW**: Manual review needed (ambiguous/low confidence)
        
        ### Confidence Levels
        
        - **0.95-1.0**: Very high - All sources agree
        - **0.85-0.94**: High - Strong evidence
        - **0.75-0.84**: Medium - Catalog match
        - **0.65-0.74**: Low - Review recommended
        
        ### Processing Modes
        
        **Catalog Mode (Recommended)**
        - Fast processing (seconds to minutes)
        - No API costs
        - Uses TF-IDF similarity
        - Good for routine operations
        
        **RAG Mode (Advanced)**
        - Deep manual search
        - Requires OpenAI API key
        - More detailed evidence
        - Use for complex cases
        
        ### Non-Defect Patterns
        
        Automatically filtered patterns:
        - Cleaning, lubrication, servicing
        - Scheduled maintenance, inspections
        - Software loads, updates
        - NFF (No Fault Found)
        - Tyre wear, oil replenishment
        
        ### Support
        
        For issues or questions:
        - Check README.md
        - Review logs in terminal
        - Contact: support@your-org.com
        """)

def _to_excel(df):
    """Convert dataframe to Excel bytes"""
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Results')
    return output.getvalue()

if __name__ == "__main__":
    main()
