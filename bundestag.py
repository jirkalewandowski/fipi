#from plpr_parser.scraper import *
import glob
import operator
import os
import codecs
import json
import pdb
import scipy as sp
from classifier import Classifier
from party_classifier import PartyClassifier
from sklearn import metrics, cross_validation
from sklearn.feature_extraction.text import CountVectorizer,TfidfTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.grid_search import GridSearchCV
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import Pipeline
from itertools import chain
from sklearn.cross_validation import StratifiedKFold
import pandas as pd
from scipy import random,unique,vstack,arange,array,mean
import cPickle
from sentiments import SentimentClassifier

DATA_PATH = os.environ.get('DATA_PATH', 'data')
TXT_DIR = os.path.join(DATA_PATH, 'txt')
OUT_DIR = os.path.join(DATA_PATH, 'out')

MINLEN_SPEECH = 1000
MINLEN = 100

partyManifestoMap = {
    'gruene':41113,
    'cducsu':41521,
    'fdp':41420,
    'spd':41320,
    'afd':41953,
    'linke':41223,
    'pirates':41952
}

bundestagParties = {
    17:['gruene','cducsu','spd','fdp','linke'],
    18:['gruene','cducsu','spd','linke']
}

bundestagGovernment = {
    17:{'government':['cducsu','fdp'],'opposition':['gruene','spd','linke']},
    18:{'government':['cducsu','spd'],'opposition':['gruene','linke']}
}

bundestagSeats = {
    17:{'gruene':68,'cducsu':239,'spd':146,'fdp':93,'linke':76},
    18:{'gruene':63,'cducsu':311,'spd':193,'linke':64}
}

def nullPrediction(parties=['linke','gruene','spd','cducsu']):
    return dict([(k, 1.0/len(parties)) for k in parties])

def get_raw_text_bundestag(folder="data/out", legislationPeriod=17):
    '''
    Loads raw text and labels from bundestag sessions
    (Preprocessed with https://github.com/bundestag/plpr-scraper, saved in json)
    '''
    data = []
    labels = []
    for f in glob.glob(folder+'/%d*.json'%legislationPeriod):
        speeches = json.load(open(f))
        for speech in speeches:
           if speech['type']=='speech' and \
            speech['speaker_party'] is not None and \
            speech['speaker_party'] in bundestagParties[legislationPeriod] and \
            len(speech['text']) > MINLEN_SPEECH:
                data.append(speech['text'])
                labels.append(speech['speaker_party'])
    return data,labels

def run_experiments():
    for legis in [17,18]:
        classify_speeches_binary_manifesto(legis);
        classify_speeches_binary_manifhes_binary_parliament(legis)
        get_sentiments(legis)

def get_sentiments(legis=17):
    trainData, trainLabels = get_raw_text_bundestag(legislationPeriod=legis)
    se = SentimentClassifier()
    sentiments = {p:[] for p in bundestagParties[legis]}
    for item in zip(trainData,trainLabels):
        sentiments[item[1]].append(se.predict(item[0]))
    sortedParties = sorted(sentiments,key=bundestagSeats[legis].get)
    sortedSentiments = [sentiments[d] for d in sortedParties]
    import pylab
    pylab.figure(figsize=(8,5))
    pylab.boxplot(sortedSentiments,labels=[p+" (%d)"%bundestagSeats[legis][p] for p in sortedParties])
    pylab.grid('on')
    #pylab.yticks(arange(len(words)),words)
    #pylab.ylim(-.2,len(words))
    #lim = max(abs(array(wordcors))) * 1.1
    #pylab.xlim(-lim,lim)
    #pylab.xticks(array([-.2,0,.2]))
    #pylab.title(party)
    #pylab.xlabel('Correlation')
    font = {'family' : 'normal', 'size'   : 16}
    pylab.rc('font', **font)
    pylab.savefig(OUT_DIR+'/party_word_correlations-%s.pdf'%party,bbox_inches='tight')

    pylab.savefig(OUT_DIR+"/sentiments-%d.pdf"%legis)

def get_stops(legislationPeriod=17,includenames=True):
    # generic stopwords
    stopwords = codecs.open("data/stopwords.txt", "r", "utf-8").readlines()[7:]
    stops = map(lambda x:x.lower().strip(),stopwords)
    names = []
    if includenames:
        # names of abgeordnete
        abgeordnete = codecs.open('data/abgeordnete-%d.txt'%legislationPeriod,encoding='utf-8').readlines()
        names = [y.strip().lower().split(' ')[0] for x in abgeordnete for y in x.split(',')]
    return unique(stops + names).tolist()

def get_word_correlations(legis=17):
    trainData, trainLabels = get_raw_text_bundestag(legislationPeriod=legis)
    stops = get_stops()
    bow = CountVectorizer(max_df=0.1,stop_words=stops).fit(trainData)
    X = bow.transform(trainData)
    wordidx2word = dict(zip(bow.vocabulary_.values(),bow.vocabulary_.keys()))
    wordCors = {}
    for pa in bundestagParties[legis]:
        party = [1.0 if x==pa else -1.0 for x in trainLabels]
        partyLabel = vstack(party)
        co = cosine_similarity(X.T,partyLabel.T - mean(partyLabel))
        wordCors[pa] = dict([(wordidx2word[x],co[x,0]) for x in co.nonzero()[0]])
    json.dump(dict(wordCors),open(OUT_DIR+'/wordCors-%d.json'%legis,'wb'))

def list_top_words(legis=17,topwhat=20):
    import pylab
    fn = OUT_DIR+'/wordCors-%d.json'%legis
    cors = json.loads(open(fn).read())
    colors = {'linke':'purple','gruene':'green','spd':'red','cducsu':'black','fdp':'yellow'}
    cors = {key:sorted(cors[key].items(), key=operator.itemgetter(1)) for key in cors.keys()}
    
    for party in cors.keys():
        pylab.figure(figsize=(3,12))
        tmp = cors[party][:topwhat] + [('...',0)] +  cors[party][-topwhat:]
        words = [x[0] for x in tmp]
        wordcors = [x[1] for x in tmp]
        pylab.barh(arange(len(words)),wordcors,color=colors[party])
        pylab.yticks(arange(len(words)),words)
        pylab.ylim(-.2,len(words))
        pylab.xticks(array([-.2,0,.02]))
        pylab.title(party)
        pylab.xlabel('Correlation')
        font = {'family' : 'normal', 'size'   : 16}
        pylab.rc('font', **font)
        pylab.savefig(OUT_DIR+'/party_word_correlations-%s-%d.pdf'%(party,legis),bbox_inches='tight')


def get_raw_text(folder="data", legislationPeriod=18):
    '''
    Loads raw text and labels from manifestoproject csv files
    (Downloaded from https://visuals.manifesto-project.wzb.eu)
    '''
    parties = bundestagParties[legislationPeriod]
    partyIds = [str(partyManifestoMap[p]) for p in parties]
    year = '2013'
    if legislationPeriod==17:year='2009'
    files = glob.glob(folder+"/[0-9]*_%s.csv"%year)
    files = filter(lambda x: x.split('/')[-1].split('_')[0] in partyIds,files)
    return zip(*chain(*filter(None,map(csv2DataTuple,files))))

def csv2DataTuple(f):
    '''
    Extracts list of tuples of (text,label) for each manifestoproject file
    '''
    df = pd.read_csv(f)
    df['content'] = df['content'].astype('str')
    partyId = f.split('/')[-1].split('_')[0]
    party = [k for (k,v) in partyManifestoMap.items() if str(v) == partyId]
    return zip(df['content'].tolist(), party * len(df))

def optimize_hyperparams(trainData,trainLabels,evalData,evalLabels, folds=2, idstr='default'):
    stops = get_stops()
    text_clf = Pipeline([('vect', CountVectorizer()),
                            ('tfidf', TfidfTransformer()),
                            ('clf',LogisticRegression(class_weight='auto'))])
    parameters = {'vect__ngram_range': [(1, 1), (1,2), (1,3)],\
           'tfidf__use_idf': (True,False),\
           'stop_words':(stops, None),\
           'clf__C': (10.**sp.arange(-1,4,1.)).tolist(),
        'vect__max_df':[0.01, 0.1, 1.0],
        'vect__min_df':[2, 5]
        }
    gs_clf = GridSearchCV(text_clf, parameters, cv=StratifiedKFold(trainLabels, folds), n_jobs=-1,verbose=4)
    best_clf = gs_clf.fit(trainData, trainLabels).best_estimator_
    # dump classifier to pickle
    cPickle.dump(best_clf, open('party_classifier.pickle','wb'),-1) 
    # test on training data with CV
    X_train, X_test, y_train, y_test = cross_validation.train_test_split(trainData, trainLabels, test_size=0.5, random_state=0)
    test_clf = text_clf.set_params(**best_clf.get_params()).fit(X_train,y_train)
    predictedTest = test_clf.predict(X_test)
    report = "*** Training Set (CVd) ***\n" + metrics.classification_report(y_test, predictedTest)
    report += '\nConfusion Matrix (rows=true, cols=predicted)\n'+', '.join(test_clf.steps[-1][1].classes_)+'\n'
    for line in metrics.confusion_matrix(y_test, predictedTest).tolist(): report += str(line)+"\n" 
    # test on held-out data
    predictedEval = best_clf.predict(evalData)
    report += "*** Evaluation Set ***\n" + metrics.classification_report(evalLabels, predictedEval)
    report += '\nConfusion Matrix (rows=true, cols=predicted)\n'+', '.join(best_clf.steps[-1][1].classes_)+'\n'
    for line in metrics.confusion_matrix(evalLabels, predictedEval).tolist(): report += str(line)+"\n" 
    report += "Pipeline-params\n"+json.dumps(best_clf.get_params())
    open(OUT_DIR+'/report-'+idstr+"-"+randid()+'.txt','wb').write(report)
    return report

def randid(N=10):
    return "".join(map(lambda x: str(x),random.randint(0,9,N).tolist()))

def classify_speeches_binary_manifesto(legislationPeriod = 18):
    evalDataParty, evalLabelsParty = get_raw_text_bundestag(legislationPeriod=legislationPeriod)
    trainDataParty, trainLabelsParty = get_raw_text(legislationPeriod=legislationPeriod)
    gov = bundestagGovernment[legislationPeriod]['government']
    trainData, trainLabels = zip(*[(x[0],'government') if x[1] in gov else (x[0],'opposition') for x in zip(trainDataParty,trainLabelsParty)])
    evalData, evalLabels = zip(*[(x[0],'government') if x[1] in gov else (x[0],'opposition') for x in zip(evalDataParty,evalLabelsParty)])
    optimize_hyperparams(trainData,trainLabels, evalData, evalLabels,idstr="manifesto-train-gov-%d"%legislationPeriod)


def classify_speeches_binary_parliament(legislationPeriod = 18):
    trainDataParty, trainLabelsParty = get_raw_text_bundestag(legislationPeriod=legislationPeriod)
    evalDataParty, evalLabelsParty = get_raw_text(legislationPeriod=legislationPeriod)
    gov = bundestagGovernment[legislationPeriod]['government']
    trainData, trainLabels = zip(*[(x[0],'government') if x[1] in gov else (x[0],'opposition') for x in zip(trainDataParty,trainLabelsParty)])
    evalData, evalLabels = zip(*[(x[0],'government') if x[1] in gov else (x[0],'opposition') for x in zip(evalDataParty,evalLabelsParty)])
    optimize_hyperparams(trainData,trainLabels, evalData, evalLabels,idstr="parliament-train-gov-%d"%legislationPeriod)

def classify_speeches_party_parliament(legislationPeriod = 18):
    trainData, trainLabels = get_raw_text_bundestag(legislationPeriod=legislationPeriod)
    evalData, evalLabels = get_raw_text(legislationPeriod=legislationPeriod)
    optimize_hyperparams(trainData,trainLabels, evalData, evalLabels,idstr="parliament-train-%d"%legislationPeriod)

def classify_speeches_party_manifesto(legislationPeriod = 18):
    evalData, evalLabels = get_raw_text_bundestag(legislationPeriod=legislationPeriod)
    trainData, trainLabels = get_raw_text(legislationPeriod=legislationPeriod)
    optimize_hyperparams(trainData,trainLabels, evalData, evalLabels,idstr="manifesto-train-%d"%legislationPeriod)

def classify_speeches_party(legislationPeriod = 18):
    from party_classifier import PartyClassifier
    #optimize_hyperparams_party(legislationPeriod)
    pclf = PartyClassifier(train=True)
    predictedParty = []
    trueParty = []
    for f in glob.glob(OUT_DIR+'/17*.json'):
        speeches = json.load(open(f))
        print "processing %d speeches in %s"%(len(speeches),f)
        for speech in speeches:
            if speech['type']=='speech' and \
            speech['speaker_party'] is not None and \
            speech['speaker_party'] in bundestagParties[legislationPeriod] and \
            len(speech['text']) > MINLEN:
                import pdb
                pdb.set_trace()
                prediction = pclf.predict(speech['text'])
                predictedParty.append(sp.argmax(prediction.values()))
                trueParty.append(prediction.keys().index(speech['speaker_party']))
    report = metrics.classification_report(trueParty, \
                predictedParty,target_names=prediction.keys())
    report += '\nConfusion Matrix (rows=true, cols=predicted)\n'+', '.join(prediction.keys())+'\n'
    for line in metrics.confusion_matrix(trueParty, predictedParty).tolist():
        report += str(line)+"\n" 
    open(OUT_DIR+'/report','wb').write(report)
    return report

def plot_leftright():
    import pylab as pl
    predTs = {
        'gruene':[],
        'cducsu':[],
        'spd':[],
        'fdp':[],
        'linke':[]
    }
    for f in glob.glob(OUT_DIR+'/17*predictions.json'):
        pred = json.load(open(f))
        for party in pred.keys():
            if len(pred[party]['leftright'])>0:
                predTs[party].append(pred[party]['leftright']['right'])
        
    pl.figure(figsize=(20,10))
    for party in pred.keys():
        predTs[party] = sp.stack(predTs[party],1)
        pl.clf()
        pl.plot(predTs[party].T)
        pl.savefig(OUT_DIR+'/partyTimeseries_'+party+'.pdf')
            

def get_party_predictions():
    pred_init = {'leftright':{},'manifestocode':{}}
    pred = {
            'gruene': {'leftright':{},'manifestocode':{}},
            'cducsu': {'leftright':{},'manifestocode':{}},
            'spd': {'leftright':{},'manifestocode':{}},
            'fdp': {'leftright':{},'manifestocode':{}},
            'linke': {'leftright':{},'manifestocode':{}}
            }
    for f in glob.glob(OUT_DIR+'/17*.json'):
        speeches = json.load(open(f))
        print "processing %d speeches in %s"%(len(speeches),f)
        for speech in speeches:
            if speech['type']=='speech' and \
            speech['speaker_party'] is not None and \
            pred.has_key(speech['speaker_party']):
                prediction = clf.predict(speech['text'])
                for prediction_type in pred_init.keys():
                    for pr in prediction[prediction_type]:
                        k = pr['label']
                        v = pr['prediction']
                        if not pred[speech['speaker_party']][prediction_type].has_key(k): 
                            pred[speech['speaker_party']][prediction_type][k] = [v]
                        else:
                            pred[speech['speaker_party']][prediction_type][k].append(v)
    for party in pred.keys():
        for prediction_type in pred[party].keys():
            for pr in pred[party][prediction_type].keys():
                pred[party][prediction_type][pr] = sp.percentile(pred[party][prediction_type][pr],[5, 25, 50, 75, 95]).tolist()
    json.dump(pred,open(OUT_DIR+'/predictions.json','wb'))

def get_party_predictions_daily():
    pred_init = {'leftright':{},'manifestocode':{}}
    for f in glob.glob(OUT_DIR+'/17*.json'):
        pred = {
                'gruene': {'leftright':{},'manifestocode':{}},
                'cducsu': {'leftright':{},'manifestocode':{}},
                'spd': {'leftright':{},'manifestocode':{}},
                'fdp': {'leftright':{},'manifestocode':{}},
                'linke': {'leftright':{},'manifestocode':{}}
                }
        speeches = json.load(open(f))
        print "processing %d speeches in %s"%(len(speeches),f)
        for speech in speeches:
            if speech['type']=='speech' and \
            speech['speaker_party'] is not None and \
            pred.has_key(speech['speaker_party']):
                prediction = clf.predict(speech['text'])
                for prediction_type in pred_init.keys():
                    for pr in prediction[prediction_type]:
                        k = pr['label']
                        v = pr['prediction']
                        if not pred[speech['speaker_party']][prediction_type].has_key(k): 
                            pred[speech['speaker_party']][prediction_type][k] = [v]
                        else:
                            pred[speech['speaker_party']][prediction_type][k].append(v)
        for party in pred.keys():
            for prediction_type in pred[party].keys():
                for pr in pred[party][prediction_type].keys():
                    pred[party][prediction_type][pr] = sp.percentile(pred[party][prediction_type][pr],[5, 25, 50, 75, 95]).tolist()
        json.dump(pred,open(f.replace(".json","-predictions.json"),'wb'))
    


def classify_all_speeches():
    for f in glob.glob(OUT_DIR+'/*.json'):
        classify_speeches(f)

def classify_speeches(f):
    data = json.load(open(f))
    data = [v for v in data if v['type'] == 'speech']
    for speech in data:
        speech['predictions'] = clf.predict(speech['text'])
    json.dump(data,open(f.replace('.json','-with-classification.json'),'wb'))

def get_all_bundestags_data():
    fetch_protokolle()
    for filename in os.listdir(TXT_DIR):
        parse_transcript_json(os.path.join(TXT_DIR, filename))

def parse_transcript_json(filename):

    wp, session = file_metadata(filename)
    with open(filename, 'rb') as fh:
        text = clean_text(fh.read())

    data = []

    base_data = {
        'filename': filename,
        'sitzung': session,
        'wahlperiode': wp
    }
    print "Loading transcript: %s/%.3d, from %s" % (wp, session, filename)
    seq = 0
    parser = SpeechParser(text.split('\n'))

    for contrib in parser:
        contrib.update(base_data)
        contrib['sequence'] = seq
        contrib['speaker_cleaned'] = clean_name(contrib['speaker'])
        contrib['speaker_fp'] = fingerprint(contrib['speaker_cleaned'])
        contrib['speaker_party'] = search_party_names(contrib['speaker'])
        seq += 1
        data.insert(0,contrib)

    jsonfile = os.path.basename(filename).replace('.txt', '.json')
    json.dump(data,open(os.path.join(OUT_DIR,jsonfile),'wb'))

 
