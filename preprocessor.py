from re import search
import numpy as np
import feather
from os.path import isfile

class preprocessor:
    
    def __init__(self, missing_value):
         self.missing_value=missing_value
         self.delim = '__'

    def get_file_type(self, file_name, debug=False):
        
        file_type = ''
        
        if search("\.npy$", file_name):
            file_type = 'npy'
        elif search("\.feather$", file_name):
            file_type = 'feather'
        elif search("\.csv$", file_name):
            file_type = 'csv'
        elif search("\.tsv$", file_name):
            file_type = 'tsv'
        else:
            file_type = None
            
        if debug:
            print(file_type)
            
        return file_type
    
    def get_default_header(self, n, prefix='C'):
        
        header = np.full(shape=n, fill_value='', dtype='<U'+str(len(str(n-1))+len(prefix)))
        for i in range(n):
            header[i] = prefix + str(i).zfill(len(str(n-1)))
            
        return header
    
    def read_file(self, file_name, has_header=True, debug=False):
        
        arr = None
        header = []
        
        if(not isfile(file_name)):
            return None
        
        if(self.get_file_type(file_name) == 'npy'):
            if debug:
                print('Reading npy file ', file_name, '...')
            arr = np.load(file_name)
            if has_header:
                header = arr[0,:]
                arr = arr[1:len(arr),:]
        
        elif(self.get_file_type(file_name) == 'feather'):
            if debug:
                print('Reading feather file ', file_name, '...')
            df = feather.read_dataframe(file_name)
            arr = df.to_numpy()
            if has_header:
                header = df.columns
        
        elif(self.get_file_type(file_name) == 'csv' or self.get_file_type(file_name) == 'tsv'):
            if debug:
                print('Reading ' + self.get_file_type(file_name) + ' file ', file_name, '...')
            
            arr = []
            if has_header:
                
                delimiter = ','
                if self.get_file_type(file_name) == 'tsv':
                    delimiter = '\t'
                arr = np.loadtxt(file_name, dtype=str, delimiter=delimiter)
                header = np.loadtxt(file_name, dtype=str, delimiter=delimiter, 
                                    comments=None, skiprows=0, max_rows=1)
                header[0] = header[0].replace('# ','')
            else:
                arr = np.loadtxt(file_name, dtype=str, delimiter=delimiter)
                
        else:
            if debug:
                print('Unknown file type for file', file_name)
                print("Returning None")
            return None
        
        if debug:
            print('  Number of samples:', arr.shape[0])
            print('  Number of features:', arr.shape[1])
            
        if len(header) == 0:
            header = self.get_default_header(arr.shape[1])
        
        return {'x':arr, 'header':header}
    
    def is_iterable(self, x):
        try:
            iter(x)
        except Exception:
            return False
        else:
            return True
    
    def is_numeric(self, x):
        
        if self.is_iterable(x):
            for ele in x:
                try:
                    float(ele)
                except: 
                    return False
        else:
            try:
                float(x)
            except: 
                return False
                
        return True
    
    def remove_na(self, x):
        
        d = x
        
        x_num = self.is_numeric(x)
        m_num = self.is_numeric(self.missing_value)
                            
        if x_num and m_num:
            idx = np.where(x.astype(float) == float(self.missing_value))
            
        else:
            idx = np.where(x.astype(str) == str(self.missing_value))
            
        if len(idx) > 0:
                d = np.delete(d,idx)
    
        return d

    
    def get_minority_class(self, x):
        
        d = self.remove_na(x)
        vs = np.unique(d)
        v0 = 0
        v1 = 0
        
        for ele in d:
            if(ele == vs[0]):
                v0+=1
            else:
                v1+=1
        
        if(v0 <= v1):
            return(vs[0])
        return(vs[1])
        
    def get_variable_type(self, x, label=None, custom_categorical=(),
                               custom_continuous=(), custom_count=(),
                               max_uniq=10, max_diff=1e-10):
        
        d = self.remove_na(x)
        n_uniq = len(set(d))
        
        if label is not None and label in custom_categorical:
            return 'categorical'
        
        if label is not None and label in custom_continuous:
            return 'continuous'
        
        if label is not None and label in custom_count:
            return 'count'
        
        if n_uniq == 1:
            return 'constant'
        
        if n_uniq == 2:
            return 'binary'
        
        if n_uniq > max_uniq and self.is_numeric(d):
            
            for ele in d:
                ele = float(ele)
                if abs(ele - round(ele)) > max_diff:
                    return 'continuous'
            return 'count'
                
        return("categorical")
                
    
    def get_metadata(self, x, header):
        
        names = ['label','type', 'min', 'max', 'zero', 'one','unique','missing']
        formats = ['<U100','<U11','float64', 'float64',str(x.dtype),str(x.dtype), str(x.dtype), '?']
        m = np.recarray(shape=x.shape[1], names=names, formats=formats)
        
        for j in range(x.shape[1]):
            
            d = self.remove_na(x[:,j])
            
            m[j]['label'] = header[j]
            
            m[j]['type'] = self.get_variable_type(d, label=header[j])
            
            if(m[j]['type'] == 'binary'):
                m[j]['one'] = self.get_minority_class(d)
                m[j]['zero'] = set(np.unique(d)).difference([m[j]['one']]).pop()
            
            if(m[j]['type'] == 'constant'):
                m[j]['zero'] = d[0]
            
            if(m[j]['type'] == 'continuous' or m[j]['type'] == 'count'):
                m[j]['min'] = np.min(d.astype(np.float))
                m[j]['max'] = np.max(d.astype(np.float))
            
            if(m[j]['type'] == 'categorical'):
               m[j]['unique'] = ','.join(np.unique(x))
            
            if(np.where(x == self.missing_value)[0] > 0):
                m[j]['missing'] = True
            else:
                m[j]['missing'] = False
            
        return m
    
    def get_one_hot_encoding(self, x, label, unique_values = None, 
                             add_missing_col=False):
        
        if unique_values is None:
            unique_values = np.unique(x)
        
        idx = np.where(unique_values == self.missing_value)[0]
        if add_missing_col:
            if len(idx) == 0:
                unique_values = np.append(unique_values, self.missing_value)
            
        n_uniq = len(unique_values)    
        u_label = []
        x_hot = np.zeros(shape=(len(x), n_uniq), dtype=int)
        
        for j in range(n_uniq):
            u_label[j] = label + self.delim + str(j)
            
            for i in range(len(x)):
                if(x[i] == unique_values[j]):
                    x_hot[i,j] = 1
            
        return {'x':x_hot, 'header':u_label}
    
    def scale(self, x):
        
        d = self.remove_na(x=x)
        x_min = np.min(d)
        x_max = np.max(d)
        s = np.zeros(shape=len(x))
        
        for i in range(len(x)):
            if x[i] != self.missing_value:
                s[i] = (x[i] - x_min) / (x_max - x_min)
            else:
                s[i] = self.missing_value
        
        return s
    
    def unscale(self, s, min_value, max_value):
        
        x = np.zeros(len(s))
        
        for i in range(len(s)):
            x[i] = s[i] * (max_value - min_value) + min_value
        return x
    
    def get_missing_column(self, x):
        
        y = np.zeros(shape=x.shape)
        idx = np.array([], dtype=int)
        
        for i in range(len(x)):
            if x[i] == self.missing_value or x[i] == str(self.missing_value):
                idx = np.append(idx, i)
            
        y[idx] = 1
        
        return y
    
    def get_na_idx(self, x):
        
        idx = np.array([])
        
        x_num = self.is_numeric(x)
        m_num = self.is_numeric(self.missing_value)
        
        for i in range(len(x)):
            if x_num and m_num:
                if float(x[i]) == float(self.missing_value):
                    idx = np.append(idx, i)
            else:
                if str(x[i]) == str(self.missing_value):
                    idx = np.append(idx, i)
                    
        return idx
    
    def get_discretized_matrix(self, x, m, header, debug=False):
        
        d_x = np.empty(shape=0)
        d_header = np.empty(shape=0)
        
        for j in range(x.shape[1]):
            
            c_type = m[j]['type']
            x_j = x[:,j]
            s_j = []
            
            #contains_missing = len(self.remove_na(x_j)) < len(x_j)
            contains_missing=True
            
            if c_type == 'constant':
                
                if contains_missing:
                    s_j = np.column_stack((np.zeros(shape=x.shape[0]),
                                           self.get_missing_column(x_j)))
                    d_header = np.append(d_header, 
                                         (header[j]+self.delim+header[j], 
                                          header[j]+self.delim+str(self.missing_value)))
                else:
                    s_j = np.zeros(shape=x.shape[0])
                    d_header = np.append(d_header, header[j])
                
            elif c_type == 'continuous' or c_type == 'count':
                
                if contains_missing:
                    idx = self.get_na_idx(x_j)
                    
                    s_j_notna = self.scale(self.remove_na(x_j).astype(np.float))
                    s_j = np.random.uniform(low=0, high=1, size=len(x_j))
                    s_j[np.setdiff1d(range(len(x_j)),idx)] = s_j_notna
                    s_j = np.column_stack((s_j,
                                       self.get_missing_column(x_j)))
                    d_header = np.append(d_header, 
                                         (header[j]+self.delim+header[j], 
                                          header[j]+self.delim+str(self.missing_value)))
                else:
                    x_j = x_j.astype(np.float)
                    s_j = self.scale(x_j)
                    d_header = np.append(d_header, header[j])
                
            elif c_type == 'categorical':
                
                res = self.get_one_hot_encoding(x=x_j, label=header[j], 
                        unique_values=','.split(m[j]['unique']), 
                        add_missing_col=True)
                s_j = res['x']
                d_header = np.append(d_header, res['header'])
                
            elif c_type == 'binary':
                
                s_j = np.zeros(shape=len(x_j), dtype=int)
                for i in range(len(x)):
                    if x[i,j] == m[j]['one']:
                        s_j[i] = 1
                
                if contains_missing:
                    f_j = s_j
                    idx = np.where(x_j == str(self.missing_value))[0]
                    f_j[idx] = np.random.randint(low=0,high=2,size=len(idx))
                    s_j = np.column_stack((f_j, self.get_missing_column(x_j)))
                    d_header = np.append(d_header, 
                                         (header[j]+self.delim+header[j], 
                                          header[j]+self.delim+str(self.missing_value)))
                else:
                    d_header = np.append(d_header, header[j])
                
            else:
                print("Warning: variable type not recognized.  Appending as is.")
                s_j = x_j
                d_header = np.append(d_header, header[j])
            
            if len(d_x) == 0:
                d_x = s_j
            else:
                d_x = np.column_stack((d_x, s_j))
                
            if debug:
                print('Dimensions of matrix are now', d_x.shape)
        
        
        return {'x':d_x, 'header':d_header}
    
    def unravel_one_hot_encoding(self, s, unique_values):
        
        x = []
       
        for i in range(len(s)):
            
            s_i = s[i,:].astype(float)
            
            idx = np.where(s_i==np.max(s_i))[0]
            if len(idx) > 1:
                idx = idx[np.random.randint(low=0,high=len(idx), size=1)]
            x = np.append(x, unique_values[idx])
            
        return x
    
    def restore_matrix(self, s, m, header):
        
        x_prime = []
        variable_names = []
        variable_values = []
        header_prime = m['label']
       
        for i in range(len(header)):
            
            splt = header[i].split('__')
            variable_names = np.append(variable_names, splt[0])
            
            if len(splt) > 1:
                variable_values = np.append(variable_values, splt[1])
            else:
                variable_values = np.append(variable_values, '')
        
        for j in range(len(m)):
            
            x_j = []
            idx_missing = []
            idx_col = np.where(variable_names == m[j]['label'])[0]
            
            if m[j]['type'] != 'categorical' and len(idx_col) > 1:
                for k in np.where(variable_names == m[j]['label'])[0]:
                    if variable_values[k] == str(self.missing_value):
                        idx_missing = np.where(s[:,k] == 1)[0]
                    else:
                        idx_col = k
                        
            s_j = s[:,idx_col]
            
            if m[j]['type'] == 'constant':
                x_j = np.full(shape=len(s), fill_value=m[j]['zero'])
                x_j[idx_missing] = self.missing_value
            
            elif m[j]['type'] == 'continuous' or m[j]['type'] == 'count':
                min_value = float(m[j]["min"])
                max_value = float(m[j]["max"])
                x_j = self.unscale(s=s_j.astype('float'), min_value=min_value, max_value=max_value)
                
                if m[j]['type'] == 'count':
                  x_j = np.round(x_j)
                  
                x_j = x_j.astype(str)
                x_j[idx_missing] = self.missing_value
            
            elif m[j]['type'] == 'categorical':
                x_j = self.unravel_one_hot_encoding(s=s_j, 
                        header=header[idx_col], unique_values=','.split(m[j]['unique']))
            
            elif m[j]['type'] == 'binary':
                
                x_j = np.full(shape=len(s), fill_value=m[j]['zero'], dtype='O')
                
                for i in range(len(s_j)):
                    if s_j[i] == 1:
                        x_j[i] = m[j]['one']
                        
                x_j[idx_missing] = self.missing_value
                        
            if len(x_prime) == 0:
                x_prime = x_j
            else: 
                x_prime = np.column_stack((x_prime, x_j))
                
        return {'x':x_prime, 'header':header_prime}
            