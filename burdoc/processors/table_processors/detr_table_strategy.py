import logging
import time
from typing import Any, Dict, List, Tuple

import torch
from PIL import Image
from transformers import (BatchFeature, DetrImageProcessor,
                          TableTransformerForObjectDetection)

from ...elements import Bbox, TableParts
from .table_extractor_strategy import TableExtractorStrategy


class DetrTableStrategy(TableExtractorStrategy):
    """Use Microsofts table-transformer to identify tables
    
    [microsoft/table-transformer-detection](https://huggingface.co/microsoft/table-transformer-detection) used for finding tables  
    [microsoft/table-transformer-structure-recognition](https://huggingface.co/microsoft/table-transformer-structure-recognition) used for
    identifying table parts

    Args:
        TableExtractorStrategy (_type_): _description_
    """


    def __init__(self, log_level: int=logging.INFO):
        super().__init__('detr', log_level=log_level)

        self.margin = 25
        self.detection_threshold = 0.9
        self.structure_threshold = 0.75
        self.extractor = DetrImageProcessor()
        self.detector_model = TableTransformerForObjectDetection.from_pretrained('microsoft/table-transformer-detection')
        self.structure_model = TableTransformerForObjectDetection.from_pretrained('microsoft/table-transformer-structure-recognition')

        if torch.cuda.is_available():
            self.logger.debug("Found CUDA")
            self.cuda = True
            self.device = torch.cuda.current_device()
            self.detector_model.to(self.device)
            self.structure_model.to(self.device)
            self.batch_size = 10
        else:
            self.cuda = False
            self.batch_size = -1


    @staticmethod
    def requirements() -> List[str]:
        return ['page_images']

    def extract_tables(self, page_numbers: List[int], page_images: Dict[int, Image.Image]) \
        -> Dict[int, List[List[Tuple[TableParts, Bbox]]]]: #type:ignore

        i = 0
        results = {}
        while i < len(page_images):
            batch_images = list(page_images.values())[i:i+self.batch_size]
            batch_page_numbers = page_numbers[i:i+self.batch_size]

            batch_results = self._extract_tables_batch(batch_images)
            for bpn,result in zip(batch_page_numbers, batch_results):
                results[bpn] = result
            i += self.batch_size

        return results
    

    def _preprocess_image(self, page_images: List[Image.Image]) -> BatchFeature:
        page_images = [i.convert("RGB") for i in page_images]
        s = time.time()
        encoding = self.extractor.preprocess(page_images, return_tensors='pt', 
                                             do_resize=True, do_rescale=True, do_normalize=True)
        self.logger.debug("Encoding %f", round(time.time() - s, 3))
        return encoding

    def _do_extraction(self, model, images: List[Image.Image], threshold: float) -> List[Dict[str, Any]]:
        features = self._preprocess_image(images)
        sizes = torch.Tensor([[i.size[1], i.size[0]] for i in images])
        if self.cuda:
            features.to(self.device)
            sizes = sizes.to(self.device) #type:ignore
        with torch.no_grad():
            start = time.time()
            outputs = model(**features)
            self.logger.debug("Model %f", round(time.perf_counter() - start, 3))
        
        start = time.perf_counter()
        results = self.extractor.post_process_object_detection(outputs, threshold=threshold, target_sizes=sizes)
        self.logger.debug("Postprocess %s", round(time.perf_counter() - start, 3))
        return results

    def _extract_tables_batch(self, page_images: List[Image.Image]) -> List[List[List[Tuple[TableParts, Bbox]]]]:
        results = self._do_extraction(self.detector_model, page_images, self.detection_threshold)

        table_images = []
        table_pages = []
        bbox_corrections = []
        for i,r in enumerate(results):
            if len(r['boxes']) > 0:
                for box in r['boxes']:
                    crop_box = [
                        max(0, int(box[0].item()-self.margin)),
                        max(0, int(box[1].item()-self.margin)),
                        min(page_images[i].size[0], int(box[2].item()+self.margin)),
                        min(page_images[i].size[1], int(box[3].item()+self.margin)),

                    ]
                    bbox_corrections.append([crop_box[0], crop_box[1]])
                    table_images.append(page_images[i].crop(crop_box))
                    table_pages.append(i)
        
        if len(table_images) == 0:
            return []

        results = self._do_extraction(self.structure_model, table_images, self.structure_threshold)

        tables: List = [[] for _ in range(len(page_images))]
        for p,c,t in zip(table_pages, bbox_corrections, results):
            tables[p].append(self._prepare_table(t,  c, *page_images[p].size)) 
        
        return tables

    def _prepare_table(self, results, corrections, page_width, page_height) \
        -> List[Tuple[TableParts, Bbox, float]]:
        """Conver the results from the DETR extraction into a list of table parts and
        bounding boxes

        Raises:
            RuntimeError: Something went wrong in the processing

        Returns:
            List[Tuple[TableParts, Bbox, float]]: Table part, containing Bbox, and score.
                The first entry should always be for the full table bbox.
        """
        parts = []
        bbox_offset_x = 3
        bbox_offset_y = 3
        for label,score,bbox in zip(results['labels'].tolist(), results['scores'].tolist(), results['boxes'].tolist()):
            corrected_bb = [bbox[0]+corrections[0]-bbox_offset_x, bbox[1]+corrections[1]-bbox_offset_y, 
                            bbox[2]+corrections[0]+bbox_offset_x, bbox[3]+corrections[1]+bbox_offset_y]
            part_type = TableParts(label)
            if part_type == TableParts.TABLE:
                table = (TableParts(label), Bbox(*corrected_bb, page_width, page_height), score) #type:ignore
            else:
                parts.append((TableParts(label), Bbox(*corrected_bb, page_width, page_height), score)) #type:ignore
        
        if not table:
            raise RuntimeError("Unexpectedly lost table bbox")
                
        return [table] + parts