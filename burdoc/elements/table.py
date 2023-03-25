from typing import Any, Dict, List, Optional, Tuple

from ..table_strategies.table_extractor_strategy import TableExtractorStrategy
from .bbox import Bbox
from .element import LayoutElement


class Table(LayoutElement):

    def __init__(self, 
                 bbox: Bbox, 
                 cells: List[List[Any]], 
                 row_headers: Optional[List[Any]]=None,
                 col_headers: Optional[List[Any]]=None,
                 row_boxes: Optional[List[Tuple[TableExtractorStrategy.TableParts, List[Bbox]]]]=None,
                 col_boxes: Optional[List[Tuple[TableExtractorStrategy.TableParts, List[Bbox]]]]=None,
                 merges: Optional[Dict[Tuple[int, int], List[Tuple[int,int]]]]=None
    ):
        super().__init__(bbox, title='Table')
        self.cells = cells
        self.row_headers = row_headers
        self.col_headers = col_headers
        self.merges = merges
        self.row_boxes = row_boxes
        self.col_boxes = col_boxes

    def _get_cell(self, row:int, col: int):
        val = {'c':self.cells[row][col]}
        if self.row_headers:
            val['rh'] = self.row_headers[row]
        if self.col_headers:
            val['ch'] = self.col_headers[col]

        return val

    def get_cell(self, row: int, col: int):
        val = {}
        if (row, col) in self.merges:
            for r,c in self.merges[(row, col)]:
                cell = self._get_cell(r, c)
                for k,cell_item in cell.items():
                    if k not in val:
                        val[k] = [cell_item]
                    else:
                        val[k].append(cell_item)
        else:
            val = self._get_cell(row, col)

        return val

    def to_html(self):
        text = "<table>"
        if self.col_headers:
            headers = [f"<th>{ch.to_html()}</th>" for ch in self.col_headers]
            text += f"<tr>{''.join(headers)}</tr>"

        for i,row in enumerate(self.cells):
            cells = []
            if self.row_headers:
                cells.append(f"<th>{self.row_headers[i]}</th>")
            cells += [f"<td>{r}</td>" for r in row]
            text += f"<tr>{''.join(cells)}</tr>"

        text += "</table>"
        return text
    
    def to_json(self, **kwargs):
        extras = {}
        if self.row_headers:
            extras['rh'] = [r.to_json() for r in self.row_headers]
        if self.col_headers:
            extras['ch'] = [c.to_json() for c in self.col_headers]
        if self.cells:
            json_cells = []
            for row in self.cells:
                json_cells.append([])
                for col in row:
                    json_cells[-1].append([l.to_json() for l in col])
            extras['cells'] = json_cells

        return super().to_json(extras=extras, **kwargs)
    
    def __str__(self):
        return f"<Table Id={self.id[:8]}... Bbox={str(self.bbox)}>"
            
        