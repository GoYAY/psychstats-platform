import unittest

from term_explainer.pdf_order import order_page


class PdfOrderTests(unittest.TestCase):
    def test_full_width_middle_material_separates_two_column_bands(self):
        labels=['L1','R1','L2','R2','FIGURE','L3','R3','L4','R4']
        positions=[(10,90,90,100),(110,90,190,100),(10,70,90,80),(110,70,190,80),
            (10,50,190,60),(10,30,90,40),(110,30,190,40),(10,10,90,20),(110,10,190,20)]
        text=''.join(v+'\n\n' for v in labels)
        boxes=[dict(text=v+'\n',bbox=b) for v,b in zip(labels,positions)]
        result,_=order_page(text,boxes,200)
        self.assertEqual(result,'L1\n\nL2\n\nR1\n\nR2\n\nFIGURE\n\nL3\n\nL4\n\nR3\n\nR4\n\n')

    def test_overlapping_full_width_material_keeps_legacy_instead_of_guessing(self):
        labels=['L1','R1','WIDE','L2','R2']
        positions=[(10,70,90,80),(110,70,190,80),(10,50,190,100),(10,20,90,30),(110,20,190,30)]
        text=''.join(v+'\n\n' for v in labels)
        result,_=order_page(text,[dict(text=v+'\n',bbox=b) for v,b in zip(labels,positions)],200)
        self.assertEqual(result,text)

    def test_running_header_shares_row_without_blocking_columns(self):
        text='page\n\nJOURNAL\n\nvolume\n\nL1\n\nR1\n\nL2\n\nR2\n\n'
        boxes=[dict(text=t+'\n',bbox=b) for t,b in [
            ('page',(5,90,25,100)),('JOURNAL',(80,90,120,100)),('volume',(170,90,195,100)),
            ('L1',(10,70,90,80)),('R1',(110,70,190,80)),
            ('L2',(10,50,90,60)),('R2',(110,50,190,60))]]
        result,_=order_page(text,boxes,200)
        self.assertEqual(result,'page\n\nJOURNAL\n\nvolume\n\nL1\n\nL2\n\nR1\n\nR2\n\n')

    def test_columns_read_down_then_across_with_full_width_header(self):
        text='HEADER\n\nL1\n\nR1\n\nL2\n\nR2\n\n'
        boxes=[dict(text=t+'\n',bbox=b) for t,b in [
            ('HEADER',(10,90,190,100)),('L1',(10,70,90,80)),
            ('R1',(110,70,190,80)),('L2',(10,50,90,60)),
            ('R2',(110,50,190,60))]]
        result,mapping=order_page(text,boxes,200)
        self.assertEqual(result,'HEADER\n\nL1\n\nL2\n\nR1\n\nR2\n\n')
        self.assertEqual(''.join(text[m['legacy_start']:m['legacy_end']] for m in mapping),result)
        self.assertEqual(sorted(i for m in mapping for i in range(m['legacy_start'],m['legacy_end'])),list(range(len(text))))

    def test_unknown_geometry_or_unmatched_text_preserves_legacy(self):
        for boxes in ([dict(text='missing',bbox=(0,0,20,20))],[dict(text='hello\n')]):
            result,mapping=order_page('hello\n',boxes,200)
            self.assertEqual(result,'hello\n')
            self.assertEqual(mapping,[dict(start=0,end=6,legacy_start=0,legacy_end=6)])
