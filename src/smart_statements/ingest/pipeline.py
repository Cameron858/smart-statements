from pathlib import Path
from typing import Literal, Self

import pandas as pd


class IngestPipeline:

    def __init__(self, df: pd.DataFrame):
        """Initialise the ingestion pipeline.

        Parameters
        ----------
        df : pandas.DataFrame
            DataFrame to ingest. A deep copy is taken to avoid mutating the
            original object.

        Raises
        ------
        TypeError
            If `df` is not a pandas DataFrame.
        """
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"`df` must be a pandas.DataFrame. Got {type(df)}")

        # store a deep copy to prevent outside mutations
        # _original must NOT be mutated
        self._df_original = df.copy(deep=True)
        self.df = df.copy(deep=True)

    @property
    def df_original(self) -> pd.DataFrame:
        """Return a deep copy of the original DataFrame.

        The getter returns a deep copy to ensure callers cannot mutate the
        stored original. The property is read-only; assigning to it will
        raise an error.
        """
        return self._df_original.copy(deep=True)

    @df_original.setter
    def df_original(self, value: pd.DataFrame) -> None:
        raise AttributeError("df_original is read-only; assignment is not allowed")

    @staticmethod
    def from_path(path: str | Path) -> "IngestPipeline":
        """Create an IngestPipeline from a file path.

        Parameters
        ----------
        path : str or pathlib.Path
            Path to an input file. Supported types: CSV, TSV, Excel
            (xls, xlsx), Parquet and JSON.

        Returns
        -------
        IngestPipeline
            Initialised pipeline containing the loaded DataFrame.

        Raises
        ------
        ValueError
            If `path` is not a str or Path, or if the file extension is
            unsupported.
        FileNotFoundError
            If the file does not exist.
        """
        if not isinstance(path, (str, Path)):
            raise ValueError(f"`path` must be str | Path. Got {type(path)}")

        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = file_path.suffix.lower()

        if ext == ".csv":
            df = pd.read_csv(file_path)
        elif ext == ".tsv":
            df = pd.read_csv(file_path, sep="\t")
        elif ext in (".xls", ".xlsx", ".xlsm", ".xlsb"):
            df = pd.read_excel(file_path)
        elif ext in (".parquet", ".pq"):
            df = pd.read_parquet(file_path)
        elif ext == ".json":
            df = pd.read_json(file_path)
        else:
            raise ValueError(f"Unsupported file extension: {ext!r}")

        return IngestPipeline(df)

    def save(self, path: str | Path):
        """Save the current DataFrame to disk.

        Parameters
        ----------
        path : str or pathlib.Path
            Destination path. Supported extensions: CSV, TSV, Excel
            (xls, xlsx), Parquet and JSON. Parent directories will be
            created if necessary.

        Returns
        -------
        IngestPipeline
            Self, to allow method chaining.

        Raises
        ------
        ValueError
            If the file extension is unsupported.
        """
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        ext = file_path.suffix.lower()

        if ext == ".csv":
            self.df.to_csv(file_path, index=False)
        elif ext == ".tsv":
            self.df.to_csv(file_path, sep="\t", index=False)
        elif ext in (".xls", ".xlsx"):
            self.df.to_excel(file_path, index=False)
        elif ext in (".parquet", ".pq"):
            self.df.to_parquet(file_path)
        elif ext == ".json":
            # write records, one per line for streaming-friendly JSON
            self.df.to_json(file_path, orient="records", lines=True)
        else:
            raise ValueError(f"Unsupported file extension: {ext!r}")

        return self

    def drop_columns(self, columns: list[str]):
        """Drop columns from the working DataFrame.

        Parameters
        ----------
        columns : list[str]
            List of column names to drop.

        Returns
        -------
        IngestPipeline
            Self, to allow method chaining.

        Raises
        ------
        TypeError
            If `columns` is not an iterable of strings.
        KeyError
            If any requested column is not present in the DataFrame.
        """
        if not isinstance(columns, (list, tuple, set)):
            raise TypeError("`columns` must be a list/tuple/set of column names")

        cols = list(columns)
        missing = set(cols) - set(self.df.columns)
        if missing:
            raise KeyError(f"Columns not found: {sorted(missing)}")

        self.df.drop(columns=cols, inplace=True)
        return self

    def drop_nans(self, rows: bool, cols: bool, how: Literal["any", "all"] = "any"):
        """Drop rows or columns with NaN values.

        Parameters
        ----------
        rows : bool
            If True, drop rows matching the ``how`` rule.
        cols : bool
            If True, drop columns matching the ``how`` rule.
        how : {'any', 'all'}, default 'any'
            Drop rows/columns where any or all values are NaN.

        Returns
        -------
        IngestPipeline
            Self, to allow method chaining.

        Raises
        ------
        TypeError
            If `rows` or `cols` is not a bool.
        ValueError
            If `how` is not ``'any'`` or ``'all'``.
        """
        if not isinstance(rows, bool):
            raise TypeError(f"`rows` must be bool. Got {type(rows)}")
        if not isinstance(cols, bool):
            raise TypeError(f"`cols` must be bool. Got {type(cols)}")
        if how not in {"any", "all"}:
            raise ValueError("`how` must be 'any' or 'all'.")

        if rows:
            self.df = self.df.dropna(axis=0, how=how)
        if cols:
            self.df = self.df.dropna(axis=1, how=how)

        return self

    def split_by_date(
        self,
        column: str,
        granularity: Literal["year", "month", "day"],
        output_dir: str | Path | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Split DataFrame by year, month or day from a datetime column.

        Parameters
        ----------
        column : str
            Name of the datetime column to split on.
        granularity : {'year', 'month', 'day'}
            Temporal granularity for splitting.
        output_dir : str, pathlib.Path or None, optional
            If provided, save each split to a CSV file in this directory.

        Returns
        -------
        dict[str, pd.DataFrame]
            Dictionary mapping granule key to DataFrame.

        Raises
        ------
        KeyError
            If ``column`` does not exist.
        TypeError
            If ``column`` is not datetime type.
        ValueError
            If ``granularity`` is not valid.
        """
        if column not in self.df.columns:
            raise KeyError(f"Column '{column}' not found")

        if not pd.api.types.is_datetime64_any_dtype(self.df[column]):
            raise TypeError(
                f"Column '{column}' must be datetime type. "
                f"Got {self.df[column].dtype}"
            )

        if granularity not in {"year", "month", "day"}:
            raise ValueError("`granularity` must be 'year', 'month', or 'day'")

        # extract temporal granule
        if granularity == "year":
            keys = self.df[column].dt.year
        elif granularity == "month":
            keys = self.df[column].dt.strftime("%Y-%m")
        else:  # day
            keys = self.df[column].dt.strftime("%Y-%m-%d")

        # group and create dict
        result = {
            str(k): group.reset_index(drop=True)
            for k, group in self.df.groupby(keys, sort=True)
        }

        # optionally save splits
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            for key, df_split in result.items():
                file_path = output_path / f"{key}.csv"
                df_split.to_csv(file_path, index=False)

        return result

    def rename_columns(self, mapper: dict[str, str]):
        """Rename columns in the working DataFrame.

        Parameters
        ----------
        mapper : dict[str, str]
            Mapping from existing column names to new names.

        Returns
        -------
        IngestPipeline
            Self, to allow method chaining.

        Raises
        ------
        TypeError
            If `mapper` is not a dict.
        KeyError
            If any key in `mapper` is not an existing column.
        """
        if not isinstance(mapper, dict):
            raise TypeError("`mapper` must be a dict mapping old->new column names")

        missing = set(mapper.keys()) - set(self.df.columns)
        if missing:
            raise KeyError(f"Columns to rename not found: {sorted(missing)}")

        self.df.rename(columns=mapper, inplace=True)

        return self
