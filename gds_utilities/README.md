# gds_utilities (moved)

The GDSII preprocessing scripts that used to live here (`gds_simplify.py`, `gds_viamerge.py`) have been superseded by **gds_prepare_for_EM**:

- GitHub: <https://github.com/VolkerMuehlhaus/gds_prepare_for_EM>
- PyPI: `pip install gds_prepare_for_EM`

It covers everything these scripts did (density-fill cutout removal, circle-like pads to octagons, via array merging clipped to the metals above/below) with newer geometry-based algorithms, and adds floating dummy fill removal and seal ring removal. The all-in-one `gds_prepare_for_EM` command runs every step in one pass:

```
source ~/venv/palace/bin/activate
pip install gds_prepare_for_EM
gds_prepare_for_EM layout.gds cleaned_layout.gds
```

setupEM's layout simplification dialog uses gds_prepare_for_EM as well.
