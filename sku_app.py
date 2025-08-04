import streamlit as st
import pandas as pd
import itertools
import re
import io
import openpyxl

st.title("Product SKU Generator")


uploaded_file = st.file_uploader("Upload product matrix (Excel)", type="xlsx")

if uploaded_file:
    sheet_names = pd.ExcelFile(uploaded_file).sheet_names
    sheet = st.selectbox("Select matrix sheet", sheet_names)

    raw_df = pd.read_excel(uploaded_file, sheet_name=sheet, header=None)

    # Find the header row by locating the row that contains 'Family'
    header_row_idx = raw_df.apply(lambda row: row.astype(str).str.contains("Family", case=False, na=False).any(), axis=1)
    header_row_idx = raw_df[header_row_idx].index
    if len(header_row_idx) == 0:
        st.error("Could not find a header row containing 'Family'.")
    else:
        header_row = header_row_idx[0]
        df = pd.read_excel(uploaded_file, sheet_name=sheet, header=header_row)

        options = { col: df[col].dropna().astype(str).str.strip().loc[lambda x: x != ""].unique().tolist()
                    for col in df.columns
                }

        all_combos = list(itertools.product(*options.values()))
        df_combos = pd.DataFrame(all_combos, columns=options.keys())

        st.subheader("Preview of Matrix")
        st.dataframe(df_combos.head(30))

        st.subheader("Define Valid Combination Restrictions")

        max_rules = 5  # Change this to allow more rule sets
        restriction_rules = []

        for i in range(max_rules):
            with st.expander(f"Restriction Rule #{i+1}", expanded=False):
                ref_col = st.selectbox(f"Condition column for rule #{i+1}", list(options.keys()), key=f"ref_col_{i}")
                ref_val = st.selectbox(f"Value in '{ref_col}' to restrict", options[ref_col], key=f"ref_val_{i}")
                
                # Choose restricted columns
                dependent_cols = [col for col in options if col != ref_col]
                rule = {"ref_col": ref_col, "ref_val": ref_val, "restrictions": {}}

                st.markdown(f"When **{ref_col} = {ref_val}**, only allow the following values:")

                for dep_col in dependent_cols:
                    allowed_vals = st.multiselect(
                        f"Allowed values for '{dep_col}'", options[dep_col], key=f"allowed_{i}_{dep_col}"
                    )
                    if allowed_vals:
                        rule["restrictions"][dep_col] = allowed_vals

                if rule["restrictions"]:
                    restriction_rules.append(rule)


        
        # Apply all restriction rules
        for rule in restriction_rules:
            ref_col = rule["ref_col"]
            ref_val = rule["ref_val"]
            restrictions = rule["restrictions"]

            # Get rows where the condition is true
            condition_rows = df_combos[df_combos[ref_col] == ref_val]

            # Start with no violations
            violations = pd.Series(False, index=condition_rows.index)

            for col, allowed_vals in restrictions.items():
                if allowed_vals:  # Only apply if values are defined
                    violations |= ~condition_rows[col].isin(allowed_vals)

            # Drop the violating rows from the full dataframe
            df_combos = df_combos.drop(index=violations[violations].index)


        #st.subheader("Filtered Combinations")
        #st.dataframe(df_combos)


        # Clean each cell and create SKU string
        def clean_cell(x):
            if pd.isnull(x):
                return ""
            x = str(x)
            x = re.sub(r"\(.*?\)", "", x)  # remove parentheses
            x = re.sub(r"[^\w\s\-/]", "", x)  # remove special characters
            x = re.sub(r"\bblank\b", "", x, flags=re.IGNORECASE)  # remove the word 'blank'
            x = x.strip()
            return x

        # Clean and concatenate
        df_cleaned = df_combos.applymap(clean_cell)
        df_cleaned["SKU"] = df_cleaned.astype(str).agg("".join, axis=1).str.replace("-/", "/", regex=False) .str.rstrip("-")

        st.subheader("Final SKU List Preview")
        st.dataframe(df_cleaned[["SKU"]])


        # In-memory Excel export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_cleaned[["SKU"]].to_excel(writer, index=False)
        output.seek(0)

        custom_filename = st.text_input("Enter file name (without extension):", value="sku_combinations")

        st.download_button(
            label="Download Filtered Combinations",
            data=output,
            file_name=f"{custom_filename.strip()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
